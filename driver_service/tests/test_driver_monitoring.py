"""
Automated unit tests for the driver-side monitoring service.
Validates all core algorithmic logic, temporal state machines, event lifecycles,
alarm management, and failure modes using synthetic data and mocks.
"""

import os
import sys
import time
import tempfile
from pathlib import Path
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

# Ensure driver_service directory is on sys.path
DRIVER_SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(DRIVER_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(DRIVER_SERVICE_DIR))

ROOT_DIR = DRIVER_SERVICE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import (
    EAR_THRESHOLD,
    DROWSINESS_DURATION_THRESHOLD,
    BLINK_MAX_DURATION,
    DROWSINESS_COOLDOWN,
    YAWN_MAR_THRESHOLD,
    YAWN_MIN_DURATION,
    YAWN_COOLDOWN,
    DRIVER_ID,
    VEHICLE_ID
)
from detection.drowsiness_detector import DrowsinessDetector
from detection.yawn_detector import YawnDetector
from detection.phone_detector import PhoneDetector
from detection.posture_detector import PostureDetector
from detection.face_detector import FaceMeshDetector, eye_aspect_ratio, mouth_ratio
from monitoring.severity_manager import SeverityManager
from monitoring.event_manager import EventManager
from monitoring.session_manager import DrivingSession
from models.events import DriverEvent
from alerts.alarm_manager import AlarmManager
from camera.camera_manager import CameraManager



class MockLandmark:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


def test_eye_aspect_ratio_geometric_calculation():
    """Validates that eye_aspect_ratio calculates vertical distances, not diagonals."""
    indices = [0, 1, 2, 3, 4, 5]
    w, h = 100, 100

    # 1. Closed Eye: Eyelids touch vertically at y=0.5
    closed_landmarks = [
        MockLandmark(0.1, 0.5), # p0 (corner)
        MockLandmark(0.3, 0.5), # p1 (top-lateral)
        MockLandmark(0.7, 0.5), # p2 (top-medial)
        MockLandmark(0.9, 0.5), # p3 (corner)
        MockLandmark(0.7, 0.5), # p4 (bot-medial)
        MockLandmark(0.3, 0.5)  # p5 (bot-lateral)
    ]
    ear_closed = eye_aspect_ratio(closed_landmarks, indices, w, h)
    assert ear_closed == 0.0, f"Closed eye EAR should be 0.0, got {ear_closed}"

    # 2. Open Eye: Height = 20px, Width = 80px -> EAR = (20 + 20) / (2 * 80) = 0.25
    open_landmarks = [
        MockLandmark(0.1, 0.5), # p0
        MockLandmark(0.3, 0.4), # p1 (top-lateral, y=40)
        MockLandmark(0.7, 0.4), # p2 (top-medial, y=40)
        MockLandmark(0.9, 0.5), # p3 (corner, x=90)
        MockLandmark(0.7, 0.6), # p4 (bot-medial, y=60)
        MockLandmark(0.3, 0.6)  # p5 (bot-lateral, y=60)
    ]
    ear_open = eye_aspect_ratio(open_landmarks, indices, w, h)
    assert abs(ear_open - 0.25) < 0.01, f"Open eye EAR should be 0.25, got {ear_open}"


# =====================================================================
# 1. Eye-Closure Threshold Behaviour
# =====================================================================
def test_eye_closure_threshold_behaviour():
    """Validates raw EAR threshold evaluation (eyes open vs closed vs None)."""
    detector = DrowsinessDetector(threshold=0.35)
    
    # Below threshold -> closed
    assert detector.is_eye_closed(0.20) is True
    assert detector.is_eye_closed(0.34) is True
    
    # At or above threshold -> open
    assert detector.is_eye_closed(0.35) is False
    assert detector.is_eye_closed(0.42) is False
    
    # None (missing face) -> must never be treated as closed
    assert detector.is_eye_closed(None) is False


# =====================================================================
# 2. Sustained Eye-Closure Timing
# =====================================================================
def test_sustained_eye_closure_timing():
    """Validates that drowsiness activates only after sustained duration threshold."""
    detector = DrowsinessDetector(threshold=0.35, duration_threshold=1.5, blink_max_duration=0.4, cooldown=2.0)
    
    base_t = 1000.0
    
    # t = 0.0s: eyes close
    res1 = detector.update(ear=0.20, current_time=base_t)
    assert res1["state"] == "BLINK"
    assert res1["is_drowsy"] is False
    assert res1["duration"] == 0.0
    
    # t = 1.0s: eyes still closed (less than 1.5s threshold)
    res2 = detector.update(ear=0.20, current_time=base_t + 1.0)
    assert res2["is_drowsy"] is False
    assert res2["duration"] == 1.0
    
    # t = 1.6s: eyes still closed (exceeds 1.5s threshold)
    res3 = detector.update(ear=0.20, current_time=base_t + 1.6)
    assert res3["state"] == "SUSTAINED_CLOSURE"
    assert res3["is_drowsy"] is True
    assert res3["duration"] == 1.6


# =====================================================================
# 3. Brief Closure (Blink) versus Prolonged Closure
# =====================================================================
def test_brief_closure_versus_prolonged_closure():
    """Validates that normal blinks (<0.4s) do not trigger drowsiness alerts."""
    detector = DrowsinessDetector(threshold=0.35, duration_threshold=1.5, blink_max_duration=0.4)
    base_t = 2000.0

    # Simulate normal 250ms blink
    detector.update(ear=0.22, current_time=base_t)
    detector.update(ear=0.21, current_time=base_t + 0.15)
    blink_res = detector.update(ear=0.38, current_time=base_t + 0.25)
    
    assert blink_res["state"] == "OPEN"
    assert blink_res["is_drowsy"] is False
    assert detector.total_blinks == 1

    # Simulate prolonged 2.0s closure
    detector.update(ear=0.20, current_time=base_t + 1.0)
    prolonged_res = detector.update(ear=0.20, current_time=base_t + 3.0)
    
    assert prolonged_res["state"] == "SUSTAINED_CLOSURE"
    assert prolonged_res["is_drowsy"] is True


# =====================================================================
# 4. Missing-Face Handling
# =====================================================================
def test_missing_face_handling():
    """Ensures missing faces reset timers safely without false drowsiness alarms."""
    detector = DrowsinessDetector(threshold=0.35, duration_threshold=1.5, missing_face_tolerance=0.3)
    base_t = 3000.0

    # Eyes close for 0.5s
    detector.update(ear=0.20, current_time=base_t)
    detector.update(ear=0.20, current_time=base_t + 0.5)

    # Face drops out of view for 0.6s (> 0.3s tolerance)
    res_missing = detector.update(ear=None, current_time=base_t + 1.1)
    assert res_missing["state"] == "OPEN"
    assert res_missing["is_drowsy"] is False
    assert detector.closure_start_time is None

    # Face detector safe handling of None frame
    face_det = FaceMeshDetector()
    detected, ear, mar, landmarks = face_det.process_frame(None)
    assert detected is False
    assert ear is None


# =====================================================================
# 5. Event Creation and Event Completion
# =====================================================================
def test_event_creation_and_completion():
    """Validates full event lifecycle: start, ongoing escalation, and completion."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        events_path = tmp.name

    try:
        session = DrivingSession(driver_id="TEST_DRV", vehicle_id="TEST_VEH")
        mgr = EventManager(events_file_path=events_path, session=session)
        
        t0 = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
        
        # Frame 1: Eyes close at t0
        mgr.process_frame_states(is_eye_closed=True, is_mouth_open=False, is_phone_detected=False, current_ear=0.20, timestamp=t0)
        assert len(mgr.all_events) == 0
        
        # Frame 2: Eyes still closed at t0 + 1.6s -> Event STARTS (active)
        t_active = t0 + timedelta(seconds=1.6)
        active_summary = mgr.process_frame_states(is_eye_closed=True, is_mouth_open=False, is_phone_detected=False, current_ear=0.18, timestamp=t_active)
        assert "DROWSINESS" in active_summary
        assert mgr.is_unsafe_active is True
        
        # Frame 3: Eyes open at t0 + 2.5s -> Event COMPLETES
        t_end = t0 + timedelta(seconds=2.5)
        mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=False, current_ear=0.38, timestamp=t_end)
        
        assert len(mgr.all_events) == 1
        completed = mgr.all_events[0]
        assert completed.event_type == "DROWSINESS"
        assert completed.duration >= 2.4
        assert completed.driver_id == "TEST_DRV"
        assert completed.vehicle_id == "TEST_VEH"
        assert completed.status in ("DROWSINESS_DETECTED", "COMPLETED", "ATTENTION_REQUIRED", "HIGH_RISK")
        assert "avg_ear" in completed.metrics
        assert completed.metrics["min_ear"] == 0.18

        # Verify session counter
        assert session.drowsiness_count == 1
    finally:
        if os.path.exists(events_path):
            os.remove(events_path)


# =====================================================================
# 6. Duplicate-Event Prevention and Cooldowns
# =====================================================================
def test_duplicate_event_prevention_and_cooldowns():
    """Validates that cooldown prevents repeated event spamming."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        events_path = tmp.name

    try:
        mgr = EventManager(events_file_path=events_path)
        mgr.conditions["DROWSINESS"].duration_threshold = 1.0
        mgr.conditions["DROWSINESS"].cooldown_duration = 3.0

        t0 = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)

        # Trigger first event (1.2s closed)
        mgr.process_frame_states(is_eye_closed=True, is_mouth_open=False, is_phone_detected=False, timestamp=t0)
        mgr.process_frame_states(is_eye_closed=True, is_mouth_open=False, is_phone_detected=False, timestamp=t0 + timedelta(seconds=1.2))
        # Eyes open -> First event ends at t0 + 1.2s
        mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=False, timestamp=t0 + timedelta(seconds=1.3))
        assert len(mgr.all_events) == 1

        # Attempt to trigger second event at t0 + 2.5s (within 3.0s cooldown)
        mgr.process_frame_states(is_eye_closed=True, is_mouth_open=False, is_phone_detected=False, timestamp=t0 + timedelta(seconds=2.5))
        mgr.process_frame_states(is_eye_closed=True, is_mouth_open=False, is_phone_detected=False, timestamp=t0 + timedelta(seconds=3.8))
        mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=False, timestamp=t0 + timedelta(seconds=3.9))
        
        # Second event should have been blocked by cooldown!
        assert len(mgr.all_events) == 1

        # Trigger after cooldown expires at t0 + 5.0s (3.8s > 3.0s after end)
        t_after_cd = t0 + timedelta(seconds=5.0)
        mgr.process_frame_states(is_eye_closed=True, is_mouth_open=False, is_phone_detected=False, timestamp=t_after_cd)
        mgr.process_frame_states(is_eye_closed=True, is_mouth_open=False, is_phone_detected=False, timestamp=t_after_cd + timedelta(seconds=1.2))
        mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=False, timestamp=t_after_cd + timedelta(seconds=1.3))
        
        # Now second event is permitted
        assert len(mgr.all_events) == 2
    finally:
        if os.path.exists(events_path):
            os.remove(events_path)


# =====================================================================
# 7. Severity Transitions
# =====================================================================
def test_severity_transitions():
    """Validates duration-based severity transitions and status classifications."""
    # Drowsiness: < 1.5s -> SAFE, 1.5s - 3.0s -> WARNING, >= 3.0s -> CRITICAL
    assert SeverityManager.evaluate_severity("DROWSINESS", duration=0.8) == "SAFE"
    assert SeverityManager.evaluate_severity("DROWSINESS", duration=1.8) == "WARNING"
    assert SeverityManager.evaluate_severity("DROWSINESS", duration=3.5) == "CRITICAL"
    assert SeverityManager.classify_status("DROWSINESS", duration=3.5, severity="CRITICAL") == "HIGH_RISK"

    # Yawning: < 2.0s -> SAFE, 2.0s - 4.0s -> WARNING, >= 4.0s -> CRITICAL
    assert SeverityManager.evaluate_severity("YAWNING", duration=1.0) == "SAFE"
    assert SeverityManager.evaluate_severity("YAWNING", duration=2.5) == "WARNING"
    assert SeverityManager.evaluate_severity("YAWNING", duration=4.2) == "CRITICAL"

    # Phone: < 1.5s -> LOW, 1.5s - 4.0s -> WARNING, >= 4.0s -> CRITICAL
    assert SeverityManager.evaluate_severity("PHONE_DETECTED", duration=0.5) == "LOW"
    assert SeverityManager.evaluate_severity("PHONE_DETECTED", duration=2.0) == "WARNING"
    assert SeverityManager.evaluate_severity("PHONE_DETECTED", duration=4.5) == "CRITICAL"


# =====================================================================
# 8. Alarm Activation and Reset Logic
# =====================================================================
def test_alarm_activation_and_reset_logic():
    """Validates alarm state transitions without requiring audio hardware."""
    alarm = AlarmManager(enabled=True)
    alarm.mixer_initialized = False # Test safe fallback mode

    assert alarm.alarm_on is False

    # Trigger unsafe condition
    alarm.update(unsafe_condition=True, severity="WARNING")
    assert alarm.alarm_on is True

    # Repeated update on next frame does not fail
    alarm.update(unsafe_condition=True, severity="CRITICAL")
    assert alarm.alarm_on is True

    # Driver returns to safe condition
    alarm.update(unsafe_condition=False)
    assert alarm.alarm_on is False

    # Reset and stop cleanly
    alarm.reset()
    alarm.stop()
    assert alarm.alarm_on is False


# =====================================================================
# 9. Configuration Validation
# =====================================================================
def test_configuration_validation():
    """Validates configuration parameters and presence of .env.example."""
    assert isinstance(EAR_THRESHOLD, float)
    assert 0.1 <= EAR_THRESHOLD <= 0.6
    assert isinstance(DROWSINESS_DURATION_THRESHOLD, float)
    assert DROWSINESS_DURATION_THRESHOLD >= 0.5
    assert isinstance(YAWN_MAR_THRESHOLD, float)
    assert isinstance(DRIVER_ID, str) and len(DRIVER_ID) > 0
    assert isinstance(VEHICLE_ID, str) and len(VEHICLE_ID) > 0

    env_example_found = (
        os.path.exists(".env.example")
        or os.path.exists(os.path.join(ROOT_DIR, ".env.example"))
        or os.path.exists(os.path.join(DRIVER_SERVICE_DIR, "config", ".env.example"))
    )
    assert env_example_found, ".env.example configuration documentation must exist"


# =====================================================================
# 10. Camera Failure and Cleanup Paths
# =====================================================================
def test_camera_failure_and_cleanup_paths():
    """Validates CameraManager handling of missing files, disconnects, and clean release."""
    # Test non-existent video file
    cam = CameraManager(source="non_existent_video_file_xyz123.mp4")
    success, msg = cam.start()
    assert success is False
    assert "not found" in msg.lower()
    assert cam.is_opened is False

    # Test safe read on unstarted camera
    read_ok, frame = cam.read()
    assert read_ok is False
    assert frame is None

    # Test idempotent release
    cam.release()
    cam.release()
    assert cam.is_opened is False


# =====================================================================
# 11. End-to-End Pipeline: EAR Calculation -> Event -> Alarm Invocation
# =====================================================================
def test_end_to_end_pipeline_drowsiness_to_alarm():
    """
    Validates complete pipeline from landmark EAR to alarm activation:
    open eyes -> eyes close -> duration accumulates -> threshold crossed -> alarm plays -> eyes open -> alarm stops.
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        events_path = tmp.name

    try:
        session = DrivingSession(driver_id="TEST_DRV", vehicle_id="TEST_VEH")
        mgr = EventManager(events_file_path=events_path, session=session)
        drowsiness_detector = DrowsinessDetector(threshold=0.21, duration_threshold=1.5)
        alarm = AlarmManager(enabled=True)
        alarm.mixer_initialized = False # test logic independent of audio device

        indices = [0, 1, 2, 3, 4, 5]
        w, h = 100, 100

        open_landmarks = [
            MockLandmark(0.1, 0.5), MockLandmark(0.3, 0.4), MockLandmark(0.7, 0.4),
            MockLandmark(0.9, 0.5), MockLandmark(0.7, 0.6), MockLandmark(0.3, 0.6)
        ]
        closed_landmarks = [
            MockLandmark(0.1, 0.5), MockLandmark(0.3, 0.5), MockLandmark(0.7, 0.5),
            MockLandmark(0.9, 0.5), MockLandmark(0.7, 0.5), MockLandmark(0.3, 0.5)
        ]

        t0 = datetime(2026, 10, 26, 14, 0, 0, tzinfo=timezone.utc)

        # Step 1: Open eyes (EAR = 0.25 > 0.21)
        ear_open = eye_aspect_ratio(open_landmarks, indices, w, h)
        assert ear_open >= 0.21
        is_closed = drowsiness_detector.is_eye_closed(ear_open)
        assert is_closed is False
        mgr.process_frame_states(is_eye_closed=is_closed, is_mouth_open=False, is_phone_detected=False, current_ear=ear_open, timestamp=t0)
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False

        # Step 2: Driver closes eyes at t0 + 0.1s (EAR = 0.0 < 0.21)
        t_close = t0 + timedelta(seconds=0.1)
        ear_closed = eye_aspect_ratio(closed_landmarks, indices, w, h)
        assert ear_closed < 0.21
        is_closed = drowsiness_detector.is_eye_closed(ear_closed)
        assert is_closed is True
        mgr.process_frame_states(is_eye_closed=is_closed, is_mouth_open=False, is_phone_detected=False, current_ear=ear_closed, timestamp=t_close)
        alarm.update(mgr.is_unsafe_active)
        # Not yet 1.5s -> alarm must still be off
        assert alarm.alarm_on is False

        # Step 3: Eyes still closed at t0 + 1.7s (1.6s of closure >= 1.5s threshold)
        t_thresh = t_close + timedelta(seconds=1.6)
        active_summary = mgr.process_frame_states(is_eye_closed=is_closed, is_mouth_open=False, is_phone_detected=False, current_ear=ear_closed, timestamp=t_thresh)
        assert "DROWSINESS" in active_summary
        assert mgr.is_unsafe_active is True

        # Pipeline alarm invocation check
        alarm.update(mgr.is_unsafe_active, severity=active_summary["DROWSINESS"]["severity"])
        assert alarm.alarm_on is True, "Alarm MUST be triggered when eye closure threshold is crossed!"

        # Step 4: Driver wakes up and reopens eyes at t0 + 2.5s
        t_reopen = t_thresh + timedelta(seconds=0.8)
        is_closed = drowsiness_detector.is_eye_closed(ear_open)
        assert is_closed is False
        mgr.process_frame_states(is_eye_closed=is_closed, is_mouth_open=False, is_phone_detected=False, current_ear=ear_open, timestamp=t_reopen)

        # Alarm deactivation check
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False, "Alarm MUST stop when eyes reopen!"
        assert len(mgr.all_events) == 1
        assert mgr.all_events[0].event_type == "DROWSINESS"

    finally:
        if os.path.exists(events_path):
            os.remove(events_path)


def test_posture_detector_geometric_evaluations():
    """Validates that PostureDetector correctly identifies UPRIGHT, HEAD_DOWN, LAYING_SIDEWAYS, and SLUMP_DOWN."""
    detector = PostureDetector(enabled=True)
    w, h = 640, 480

    def make_landmarks(forehead, nose, chin, left_eye, right_eye, left_mouth=(0.45, 0.60), right_mouth=(0.55, 0.60)):
        # Construct mock map of 468 landmarks
        lm = {}
        for i in range(468):
            lm[i] = MockLandmark(0.5, 0.5)
        lm[10] = MockLandmark(forehead[0], forehead[1])  # Forehead
        lm[1] = MockLandmark(nose[0], nose[1])          # Nose tip
        lm[152] = MockLandmark(chin[0], chin[1])        # Chin
        lm[33] = MockLandmark(left_eye[0], left_eye[1]) # Left eye outer
        lm[263] = MockLandmark(right_eye[0], right_eye[1]) # Right eye outer
        lm[61] = MockLandmark(left_mouth[0], left_mouth[1]) # Left mouth
        lm[291] = MockLandmark(right_mouth[0], right_mouth[1]) # Right mouth
        return lm

    # 1. Upright Normal Driver Posture
    upright_lm = make_landmarks(
        forehead=(0.50, 0.25),
        nose=(0.50, 0.45),
        chin=(0.50, 0.65),
        left_eye=(0.42, 0.38),
        right_eye=(0.58, 0.38)
    )
    is_unsafe, state, metrics = detector.evaluate_posture(upright_lm, (h, w))
    assert is_unsafe is False
    assert state == "UPRIGHT"
    assert abs(metrics["roll"]) < 5.0
    assert metrics["ratio"] >= 0.8

    # 2. Head Slump Forward / Nodding Down (chin compressed towards nose)
    head_down_lm = make_landmarks(
        forehead=(0.50, 0.25),
        nose=(0.50, 0.49),
        chin=(0.50, 0.54), # chin-nose is only 0.05, forehead-nose is 0.24 (ratio ~ 0.21)
        left_eye=(0.42, 0.43),
        right_eye=(0.58, 0.43)
    )
    is_unsafe, state, metrics = detector.evaluate_posture(head_down_lm, (h, w))
    assert is_unsafe is True
    assert state == "HEAD_DOWN"
    assert metrics["ratio"] < 0.48

    # 3. Head Laying Sideways (eye line tilted 35 degrees)
    sideways_lm = make_landmarks(
        forehead=(0.50, 0.25),
        nose=(0.50, 0.45),
        chin=(0.50, 0.65),
        left_eye=(0.42, 0.32),
        right_eye=(0.58, 0.44) # dy = 0.12, dx = 0.16 -> ~37 degrees
    )
    is_unsafe, state, metrics = detector.evaluate_posture(sideways_lm, (h, w))
    assert is_unsafe is True
    assert state == "LAYING_SIDEWAYS"
    assert abs(metrics["roll"]) >= 28.0

    # 4. Slumped Down into Steering Wheel (nose position drops into bottom frame)
    slump_lm = make_landmarks(
        forehead=(0.50, 0.55),
        nose=(0.50, 0.75), # Nose vertical position = 0.75 >= 0.68
        chin=(0.50, 0.95),
        left_eye=(0.42, 0.68),
        right_eye=(0.58, 0.68)
    )
    is_unsafe, state, metrics = detector.evaluate_posture(slump_lm, (h, w))
    assert is_unsafe is True
    assert state == "SLUMP_DOWN"


def test_posture_detector_temporal_tracking():
    """Validates that unsafe posture must persist >= 1.5s to confirm event."""
    detector = PostureDetector(duration_threshold=1.5, cooldown=3.0)

    # Mock head down landmarks
    lm = {i: MockLandmark(0.5, 0.5) for i in range(468)}
    lm[10] = MockLandmark(0.50, 0.25)
    lm[1] = MockLandmark(0.50, 0.49)
    lm[152] = MockLandmark(0.50, 0.54)
    lm[33] = MockLandmark(0.42, 0.43)
    lm[263] = MockLandmark(0.58, 0.43)

    t0 = 1000.0
    # At t0: Unsafe detected, but duration is 0.0s (not yet confirmed)
    res0 = detector.update(lm, current_time=t0)
    assert res0["is_unhealthy_posture"] is True
    assert res0["is_head_down"] is False

    # At t0 + 0.8s: Brief glance or adjustment, still under 1.5s
    res1 = detector.update(lm, current_time=t0 + 0.8)
    assert res1["is_unhealthy_posture"] is True
    assert res1["is_head_down"] is False

    # At t0 + 1.6s: Sustained head slump >= 1.5s -> confirmed event
    res2 = detector.update(lm, current_time=t0 + 1.6)
    assert res2["is_unhealthy_posture"] is True
    assert res2["is_head_down"] is True
    assert res2["duration"] >= 1.5


def test_head_down_lay_down_pipeline_alarm_trigger():
    """End-to-end integration: validates that sustained head-down / lay-down triggers local alarm."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        events_path = tf.name

    try:
        mgr = EventManager(events_file_path=events_path)
        alarm = AlarmManager(enabled=True)
        alarm._init_audio = MagicMock()
        alarm.alarm_on = False

        t0 = datetime(2026, 10, 26, 15, 0, 0, tzinfo=timezone.utc)

        # 1. Driver upright
        mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=False, is_head_down=False, timestamp=t0)
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False

        # 2. Driver slumps forward / lays head down at t0 + 0.1s
        t_slump = t0 + timedelta(seconds=0.1)
        mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=False, is_head_down=True, timestamp=t_slump)
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False # Under threshold

        # 3. Head remains down for 1.6s (>= 1.5s threshold)
        t_thresh = t_slump + timedelta(seconds=1.6)
        active_summary = mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=False, is_head_down=True, timestamp=t_thresh)
        assert "HEAD_DOWN" in active_summary
        assert mgr.is_unsafe_active is True

        alarm.update(mgr.is_unsafe_active, severity=active_summary["HEAD_DOWN"]["severity"])
        assert alarm.alarm_on is True, "Local audio alarm MUST trigger when driver lays head down!"

        # 4. Driver sits back up
        t_up = t_thresh + timedelta(seconds=0.5)
        mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=False, is_head_down=False, timestamp=t_up)
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False, "Alarm MUST stop when driver sits upright!"

        assert len(mgr.all_events) == 1
        assert mgr.all_events[0].event_type == "HEAD_DOWN"
        assert mgr.all_events[0].status == "UNSAFE_POSTURE"

    finally:
        if os.path.exists(events_path):
            os.remove(events_path)


def test_phone_detection_pipeline_alarm_trigger():
    """End-to-end integration: validates that sustained mobile phone usage triggers local alarm."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        events_path = tf.name

    try:
        mgr = EventManager(events_file_path=events_path)
        alarm = AlarmManager(enabled=True)
        alarm._init_audio = MagicMock()
        alarm.alarm_on = False

        t0 = datetime(2026, 10, 26, 16, 0, 0, tzinfo=timezone.utc)

        # 1. No phone visible
        mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=False, timestamp=t0)
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False

        # 2. Phone detected in hand
        t_phone = t0 + timedelta(seconds=0.1)
        mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=True, phone_conf=0.88, timestamp=t_phone)
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False # Under threshold

        # 3. Sustained phone usage >= 1.5s
        t_thresh = t_phone + timedelta(seconds=1.6)
        active_summary = mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=True, phone_conf=0.91, timestamp=t_thresh)
        assert "PHONE_DETECTED" in active_summary
        assert mgr.is_unsafe_active is True

        alarm.update(mgr.is_unsafe_active, severity=active_summary["PHONE_DETECTED"]["severity"])
        assert alarm.alarm_on is True, "Local audio alarm MUST trigger when mobile phone is used!"

        # 4. Driver puts phone away
        t_away = t_thresh + timedelta(seconds=0.5)
        mgr.process_frame_states(is_eye_closed=False, is_mouth_open=False, is_phone_detected=False, timestamp=t_away)
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False, "Alarm MUST stop when phone is put away!"

        assert len(mgr.all_events) == 1
        assert mgr.all_events[0].event_type == "PHONE_DETECTED"
        assert mgr.all_events[0].status == "ATTENTION_REQUIRED"

    finally:
        if os.path.exists(events_path):
            os.remove(events_path)

