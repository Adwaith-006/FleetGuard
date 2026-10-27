"""
Unit and integration tests for Phone Detection and Yawning Detection.
Tests feature extraction, temporal tracking, class filtering, confidence/IoU thresholding,
failure handling, independent detection, and full event/alarm pipeline.
"""

import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest

# Ensure driver_service directory and repo root are in sys.path
DRIVER_SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(DRIVER_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(DRIVER_SERVICE_DIR))

ROOT_DIR = DRIVER_SERVICE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from detection.phone_detector import PhoneDetector
from detection.yawn_detector import YawnDetector
from detection.face_detector import mouth_ratio, euclidean_distance
from monitoring.event_manager import EventManager
from monitoring.session_manager import DrivingSession
from alerts.alarm_manager import AlarmManager


class MockPoint:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class MockBox:
    def __init__(self, cls_id: int, conf: float, xyxy: list):
        self.cls = [cls_id]
        self.conf = [conf]
        self.xyxy = [xyxy]


class MockResult:
    def __init__(self, boxes):
        self.boxes = boxes


# =====================================================================
# 1. Phone Detection Tests
# =====================================================================

def test_phone_detector_disabled_by_config():
    """Validates that PhoneDetector stays disabled when enabled=False."""
    detector = PhoneDetector(enabled=False)
    assert detector.enabled is False
    assert detector.is_available is False
    assert "Disabled" in detector.status_reason

    detected, conf, boxes = detector.detect(MagicMock())
    assert detected is False
    assert conf is None
    assert boxes == []


def test_phone_detector_missing_weights_graceful():
    """Validates that missing model weights disable phone detection without crashing."""
    detector = PhoneDetector(
        model_path="non_existent_weights_xyz123.pt",
        enabled=True
    )
    assert detector.is_available is False
    assert "not found" in detector.status_reason.lower()

    detected, conf, boxes = detector.detect(MagicMock())
    assert detected is False
    assert conf is None
    assert boxes == []


def test_phone_detector_unsupported_model_classes():
    """Validates that a model without a phone class is marked unavailable."""
    with patch("detection.phone_detector.YOLO") as mock_yolo_cls:
        mock_instance = MagicMock()
        mock_instance.names = {0: "car", 1: "bicycle", 2: "dog"}
        mock_yolo_cls.return_value = mock_instance

        with patch("os.path.exists", return_value=True):
            detector = PhoneDetector(model_path="dummy.pt", enabled=True)
            assert detector.is_available is False
            assert "no cell phone class" in detector.status_reason.lower()


def test_phone_detector_recognizes_phone_class():
    """Validates that cell phone detections above threshold return True with bbox and conf."""
    with patch("detection.phone_detector.YOLO") as mock_yolo_cls:
        mock_instance = MagicMock()
        mock_instance.names = {0: "person", 67: "cell phone", 39: "bottle"}
        mock_yolo_cls.return_value = mock_instance

        with patch("os.path.exists", return_value=True):
            detector = PhoneDetector(
                model_path="dummy.pt",
                conf_threshold=0.45,
                iou_threshold=0.45,
                enabled=True
            )
            assert detector.is_available is True
            assert 67 in detector.phone_class_ids

            # Simulate frame with cell phone detection
            mock_box = MockBox(cls_id=67, conf=0.88, xyxy=[100, 150, 220, 340])
            mock_instance.return_value = [MockResult(boxes=[mock_box])]

            frame = MagicMock()
            detected, conf, boxes = detector.detect(frame)
            assert detected is True
            assert conf == 0.88
            assert len(boxes) == 1
            assert boxes[0] == (100, 150, 220, 340, 0.88)


def test_phone_detector_filters_unrelated_classes():
    """Validates that non-phone objects (person, bottle, etc.) do NOT trigger phone detection."""
    with patch("detection.phone_detector.YOLO") as mock_yolo_cls:
        mock_instance = MagicMock()
        mock_instance.names = {0: "person", 67: "cell phone", 39: "bottle"}
        mock_yolo_cls.return_value = mock_instance

        with patch("os.path.exists", return_value=True):
            detector = PhoneDetector(model_path="dummy.pt", conf_threshold=0.45, enabled=True)

            # Person and bottle detected with high confidence
            box_person = MockBox(cls_id=0, conf=0.92, xyxy=[50, 50, 300, 400])
            box_bottle = MockBox(cls_id=39, conf=0.85, xyxy=[320, 200, 380, 350])
            mock_instance.return_value = [MockResult(boxes=[box_person, box_bottle])]

            detected, conf, boxes = detector.detect(MagicMock())
            assert detected is False
            assert conf is None
            assert boxes == []


def test_phone_detector_filters_low_confidence():
    """Validates that phone detections below conf_threshold are filtered out."""
    with patch("detection.phone_detector.YOLO") as mock_yolo_cls:
        mock_instance = MagicMock()
        mock_instance.names = {67: "cell phone"}
        mock_yolo_cls.return_value = mock_instance

        with patch("os.path.exists", return_value=True):
            detector = PhoneDetector(model_path="dummy.pt", conf_threshold=0.50, enabled=True)

            # Cell phone with low confidence (0.35 < 0.50)
            mock_box = MockBox(cls_id=67, conf=0.35, xyxy=[100, 100, 200, 200])
            mock_instance.return_value = [MockResult(boxes=[mock_box])]

            detected, conf, boxes = detector.detect(MagicMock())
            assert detected is False
            assert conf is None
            assert boxes == []


def test_phone_detection_independent_of_face():
    """Validates that phone detection activates even when face is not detected."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        events_path = tf.name

    try:
        session = DrivingSession(driver_id="TEST_DRV", vehicle_id="TEST_VEH")
        mgr = EventManager(events_file_path=events_path, session=session)
        alarm = AlarmManager(enabled=True)
        alarm._init_audio = MagicMock()
        alarm.alarm_on = False

        t0 = datetime(2026, 10, 27, 3, 0, 0, tzinfo=timezone.utc)

        # Frame 1: Face is NOT detected (None), but phone IS detected
        mgr.process_frame_states(
            is_eye_closed=False,
            is_mouth_open=False,
            is_phone_detected=True,
            current_ear=None,
            phone_conf=0.85,
            timestamp=t0
        )
        assert mgr.is_unsafe_active is False  # Not yet 1.5s

        # Frame 2: 1.6s later, still holding phone, face still not detected
        t_thresh = t0 + timedelta(seconds=1.6)
        active_summary = mgr.process_frame_states(
            is_eye_closed=False,
            is_mouth_open=False,
            is_phone_detected=True,
            current_ear=None,
            phone_conf=0.90,
            timestamp=t_thresh
        )
        assert "PHONE_DETECTED" in active_summary
        assert mgr.is_unsafe_active is True

        alarm.update(mgr.is_unsafe_active, severity=active_summary["PHONE_DETECTED"]["severity"])
        assert alarm.alarm_on is True

        # Frame 3: Driver puts phone away
        t_away = t_thresh + timedelta(seconds=0.5)
        mgr.process_frame_states(
            is_eye_closed=False,
            is_mouth_open=False,
            is_phone_detected=False,
            timestamp=t_away
        )
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False

        assert len(mgr.all_events) == 1
        assert mgr.all_events[0].event_type == "PHONE_DETECTED"
    finally:
        if os.path.exists(events_path):
            os.remove(events_path)


# =====================================================================
# 2. Yawning Detection Tests
# =====================================================================

def test_mouth_ratio_geometric_calculation():
    """Validates that mouth_ratio calculates height / width using Euclidean distances."""
    w, h = 640, 480

    def make_mouth_landmarks(upper_y, lower_y, left_x=0.40, right_x=0.60):
        lm = {i: MockPoint(0.5, 0.5) for i in range(468)}
        lm[13] = MockPoint(0.50, upper_y)  # Upper lip inner
        lm[14] = MockPoint(0.50, lower_y)  # Lower lip inner
        lm[61] = MockPoint(left_x, 0.60)   # Left corner
        lm[291] = MockPoint(right_x, 0.60) # Right corner
        return lm

    # 1. Closed Mouth: lips touching (height ~0, width = 0.20 * 640 = 128px)
    closed_lm = make_mouth_landmarks(upper_y=0.60, lower_y=0.60)
    mar_closed = mouth_ratio(closed_lm, w, h)
    assert mar_closed == 0.0

    # 2. Normal Speaking / Smiling: height = 0.04 * 480 = 19.2px, width = 128px -> MAR = 19.2 / 128 = 0.15
    speaking_lm = make_mouth_landmarks(upper_y=0.58, lower_y=0.62)
    mar_speaking = mouth_ratio(speaking_lm, w, h)
    assert abs(mar_speaking - 0.15) < 0.02
    assert mar_speaking < 0.50, "Speech/smile MAR must be well below yawn threshold"

    # 3. Wide Yawn: height = 0.16 * 480 = 76.8px, width = 128px -> MAR = 76.8 / 128 = 0.60
    yawn_lm = make_mouth_landmarks(upper_y=0.52, lower_y=0.68)
    mar_yawn = mouth_ratio(yawn_lm, w, h)
    assert abs(mar_yawn - 0.60) < 0.02
    assert mar_yawn >= 0.50, "Wide yawn MAR must meet/exceed calibrated threshold"

    # 4. Zero width protection
    zero_w_lm = make_mouth_landmarks(upper_y=0.52, lower_y=0.68, left_x=0.50, right_x=0.50)
    assert mouth_ratio(zero_w_lm, w, h) == 0.0

    # 5. Invalid / None landmark protection
    assert mouth_ratio(None, w, h) == 0.0
    assert mouth_ratio({}, w, h) == 0.0


def test_yawn_detector_mar_below_threshold():
    """Validates that MAR below threshold remains in CLOSED state and does not trigger."""
    detector = YawnDetector(mar_threshold=0.50, duration_threshold=2.0)
    res = detector.update(mar=0.32, current_time=1000.0)

    assert res["state"] == "CLOSED"
    assert res["is_yawning"] is False
    assert res["duration"] == 0.0
    assert detector.is_mouth_open(0.32) is False


def test_yawn_detector_brief_opening_speech_filter():
    """Validates that mouth openings shorter than duration_threshold (< 2.0s) do not trigger a yawn."""
    detector = YawnDetector(mar_threshold=0.50, duration_threshold=2.0)
    t0 = 2000.0

    # Mouth opens wide (MAR = 0.58)
    res1 = detector.update(mar=0.58, current_time=t0)
    assert res1["state"] == "TALKING"
    assert res1["is_yawning"] is False

    # 1.2s of open mouth (still under 2.0s minimum duration)
    res2 = detector.update(mar=0.58, current_time=t0 + 1.2)
    assert res2["state"] == "TALKING"
    assert res2["is_yawning"] is False
    assert res2["duration"] == 1.2


def test_yawn_detector_sustained_yawn_triggers():
    """Validates that mouth opening >= 2.0s triggers confirmed yawn event."""
    detector = YawnDetector(mar_threshold=0.50, duration_threshold=2.0, cooldown=3.0)
    t0 = 3000.0

    detector.update(mar=0.55, current_time=t0)
    detector.update(mar=0.55, current_time=t0 + 1.5)

    # Reaches 2.1s >= 2.0s threshold
    res_confirmed = detector.update(mar=0.55, current_time=t0 + 2.1)
    assert res_confirmed["state"] == "YAWNING"
    assert res_confirmed["is_yawning"] is True
    assert res_confirmed["duration"] == 2.1


def test_yawn_detector_mouth_closure_resets_timer():
    """Validates that closing mouth resets open duration timer."""
    detector = YawnDetector(mar_threshold=0.50, duration_threshold=2.0)
    t0 = 4000.0

    # Open mouth for 1.5s
    detector.update(mar=0.55, current_time=t0)
    detector.update(mar=0.55, current_time=t0 + 1.5)
    assert detector.open_start_time is not None

    # Mouth closes (MAR = 0.20)
    res_closed = detector.update(mar=0.20, current_time=t0 + 1.7)
    assert res_closed["state"] == "CLOSED"
    assert res_closed["is_yawning"] is False
    assert res_closed["duration"] == 0.0
    assert detector.open_start_time is None


def test_yawn_detector_cooldown_prevents_duplicate():
    """Validates that cooldown suppresses immediate consecutive triggers."""
    detector = YawnDetector(mar_threshold=0.50, duration_threshold=2.0, cooldown=3.0)
    t0 = 5000.0

    # Trigger first yawn
    detector.update(mar=0.55, current_time=t0)
    detector.update(mar=0.55, current_time=t0 + 2.1)
    detector.trigger_event_cooldown(current_time=t0 + 2.1)

    # Next frame at t0 + 2.5s (within 3.0s cooldown)
    res_cooldown = detector.update(mar=0.55, current_time=t0 + 2.5)
    assert res_cooldown["in_cooldown"] is True
    assert res_cooldown["is_yawning"] is False


def test_yawn_detector_missing_face_resets_safely():
    """Validates that missing face landmarks reset open timer without false alarm."""
    detector = YawnDetector(mar_threshold=0.50, duration_threshold=2.0, missing_face_tolerance=0.35)
    t0 = 6000.0

    detector.update(mar=0.55, current_time=t0)
    detector.update(mar=0.55, current_time=t0 + 1.0)

    # Face drops out for 0.5s (> 0.35s tolerance)
    res_missing = detector.update(mar=None, current_time=t0 + 1.6)
    assert res_missing["state"] == "CLOSED"
    assert res_missing["is_yawning"] is False
    assert detector.open_start_time is None


def test_end_to_end_yawning_pipeline_to_alarm_and_events():
    """
    Validates complete end-to-end pipeline:
    Mouth opens -> persists >= 2.0s -> EventManager records YAWNING ->
    Alarm triggers -> mouth closes -> event persisted to JSON with MAR metrics -> Alarm stops.
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        events_path = tf.name

    try:
        session = DrivingSession(driver_id="TEST_DRV", vehicle_id="TEST_VEH")
        mgr = EventManager(events_file_path=events_path, session=session)
        alarm = AlarmManager(enabled=True)
        alarm._init_audio = MagicMock()
        alarm.alarm_on = False

        t0 = datetime(2026, 10, 27, 4, 0, 0, tzinfo=timezone.utc)

        # Step 1: Normal closed mouth (MAR = 0.15)
        mgr.process_frame_states(
            is_eye_closed=False,
            is_mouth_open=False,
            is_phone_detected=False,
            mouth_dist=0.15,
            timestamp=t0
        )
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False

        # Step 2: Driver begins yawning at t0 + 0.1s (MAR = 0.58)
        t_yawn = t0 + timedelta(seconds=0.1)
        mgr.process_frame_states(
            is_eye_closed=False,
            is_mouth_open=True,
            is_phone_detected=False,
            mouth_dist=0.58,
            timestamp=t_yawn
        )
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False  # Not yet 2.0s

        # Step 3: Yawn sustained for 2.1s (>= 2.0s threshold)
        t_thresh = t_yawn + timedelta(seconds=2.1)
        active_summary = mgr.process_frame_states(
            is_eye_closed=False,
            is_mouth_open=True,
            is_phone_detected=False,
            mouth_dist=0.62,
            timestamp=t_thresh
        )
        assert "YAWNING" in active_summary
        assert mgr.is_unsafe_active is True

        # Pipeline alarm trigger
        alarm.update(mgr.is_unsafe_active, severity=active_summary["YAWNING"]["severity"])
        assert alarm.alarm_on is True, "Alarm MUST trigger when yawn exceeds duration threshold!"

        # Step 4: Driver finishes yawn and closes mouth
        t_close = t_thresh + timedelta(seconds=0.5)
        mgr.process_frame_states(
            is_eye_closed=False,
            is_mouth_open=False,
            is_phone_detected=False,
            mouth_dist=0.15,
            timestamp=t_close
        )
        alarm.update(mgr.is_unsafe_active)
        assert alarm.alarm_on is False, "Alarm MUST deactivate when mouth closes!"

        # Verify event persistence and metric summaries
        assert len(mgr.all_events) == 1
        yawn_event = mgr.all_events[0]
        assert yawn_event.event_type == "YAWNING"
        assert yawn_event.status in ("ATTENTION_REQUIRED", "COMPLETED", "WARNING")
        assert "max_mar" in yawn_event.metrics
        assert yawn_event.metrics["max_mar"] == 0.62
        assert "avg_mar" in yawn_event.metrics
        assert session.yawning_count == 1

    finally:
        if os.path.exists(events_path):
            os.remove(events_path)
