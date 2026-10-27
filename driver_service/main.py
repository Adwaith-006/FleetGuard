import argparse
import os
import sys
from pathlib import Path
from typing import Optional
import cv2

# Ensure driver_service directory and project root are in sys.path
SERVICE_DIR = Path(__file__).resolve().parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

ROOT_DIR = SERVICE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import (
    VIDEO_SOURCE,
    DRIVER_ID,
    VEHICLE_ID,
    ALARM_ENABLED,
    ENABLE_PHONE_DETECTION,
    ENABLE_POSTURE_DETECTION,
    EAR_THRESHOLD,
    DROWSINESS_DURATION_THRESHOLD,
    HEAD_DOWN_DURATION_THRESHOLD,
    YAWN_MAR_THRESHOLD,
    YAWN_MIN_DURATION,
    YAWN_COOLDOWN,
    PHONE_CONFIDENCE_THRESHOLD,
    MOUTH_OPEN_THRESHOLD,
    YAWN_DURATION_THRESHOLD
)
from utils.logger import logger
from camera.camera_manager import CameraManager
from utils.visualizer import HUDVisualizer
from detection.face_detector import FaceMeshDetector
from detection.phone_detector import PhoneDetector
from detection.drowsiness_detector import DrowsinessDetector
from detection.yawn_detector import YawnDetector
from detection.posture_detector import PostureDetector
from monitoring.event_manager import EventManager
from monitoring.session_manager import DrivingSession
from alerts.alarm_manager import AlarmManager
from monitoring.temporal_tracker import TemporalEvidenceTracker
from utils.api_client import send_status_to_backend_async



def parse_arguments():
    """Parses command-line arguments for the monitoring service."""
    parser = argparse.ArgumentParser(
        description="Vehicle-Side AI Driver Behaviour & Safety Monitoring System"
    )
    parser.add_argument(
        "-s", "--source",
        default=VIDEO_SOURCE,
        help="Camera index (e.g. 0, 1) or path to prerecorded video file (e.g. test.mp4)"
    )
    parser.add_argument(
        "--driver-id",
        default=DRIVER_ID,
        help=f"Driver identifier (default: {DRIVER_ID})"
    )
    parser.add_argument(
        "--vehicle-id",
        default=VEHICLE_ID,
        help=f"Vehicle identifier (default: {VEHICLE_ID})"
    )
    parser.add_argument(
        "--no-alarm",
        action="store_true",
        help="Disable local audio alarm"
    )
    parser.add_argument(
        "--no-phone",
        action="store_true",
        help="Disable phone detection"
    )
    parser.add_argument(
        "--no-posture",
        action="store_true",
        help="Disable head down / lay down posture detection"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without displaying OpenCV GUI window"
    )
    parser.add_argument(
        "--ear-threshold",
        type=float,
        default=EAR_THRESHOLD,
        help=f"Eye Aspect Ratio closure threshold (default: {EAR_THRESHOLD})"
    )
    parser.add_argument(
        "--mar-threshold",
        type=float,
        default=YAWN_MAR_THRESHOLD,
        help=f"Mouth Aspect Ratio yawn threshold (default: {YAWN_MAR_THRESHOLD})"
    )
    parser.add_argument(
        "--phone-conf",
        type=float,
        default=PHONE_CONFIDENCE_THRESHOLD,
        help=f"YOLO phone detection confidence threshold (default: {PHONE_CONFIDENCE_THRESHOLD})"
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional maximum number of frames to process before exiting (useful for testing)"
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    logger.info("=" * 60)
    logger.info("AI FLEET DRIVER BEHAVIOUR & SAFETY MONITORING SERVICE")
    logger.info(f"Driver ID: {args.driver_id} | Vehicle ID: {args.vehicle_id} | Source: {args.source}")
    logger.info(
        f"Thresholds: EAR <= {args.ear_threshold:.2f} | MAR >= {args.mar_threshold:.2f} | "
        f"Phone Conf >= {args.phone_conf:.2f} | Drowsiness >= {DROWSINESS_DURATION_THRESHOLD}s | "
        f"Head Down >= {HEAD_DOWN_DURATION_THRESHOLD}s"
    )
    logger.info("=" * 60)

    # 1. Initialize Managers and Detectors
    session = DrivingSession(driver_id=args.driver_id, vehicle_id=args.vehicle_id)
    event_manager = EventManager(session=session, driver_id=args.driver_id, vehicle_id=args.vehicle_id)
    
    alarm_enabled = ALARM_ENABLED and not args.no_alarm
    alarm_manager = AlarmManager(enabled=alarm_enabled)

    face_detector = FaceMeshDetector()
    drowsiness_detector = DrowsinessDetector(threshold=args.ear_threshold)
    yawn_detector = YawnDetector(mar_threshold=args.mar_threshold)

    phone_detection_enabled = ENABLE_PHONE_DETECTION and not args.no_phone
    phone_detector = PhoneDetector(conf_threshold=args.phone_conf, enabled=phone_detection_enabled)

    posture_detection_enabled = ENABLE_POSTURE_DETECTION and not args.no_posture
    posture_detector = PostureDetector(enabled=posture_detection_enabled)

    logger.info(f"Driving Session ID: {session.session_id}")
    logger.info(f"Face Mesh: {'Available' if face_detector.is_available else 'Unavailable (Disabled)'}")
    logger.info(f"Phone Detection: {'Active' if phone_detector.is_available else phone_detector.status_reason}")
    logger.info(f"Posture Detection: {'Active' if posture_detection_enabled else 'Disabled'}")
    logger.info(f"Audio Alarm: {'Enabled' if alarm_enabled else 'Disabled'}")

    # 2. Initialize Camera Capture
    camera_manager = CameraManager(source=args.source)
    opened, err = camera_manager.start()
    if not opened:
        logger.error(f"Cannot initialize camera or video source: {err}")
        send_status_to_backend_async({
            "driver_id": args.driver_id,
            "vehicle_id": args.vehicle_id,
            "status": "UNAVAILABLE",
            "monitoring_state": "Detector initialization failed"
        })
        sys.exit(1)

    logger.info("Monitoring active. Press 'q' in the camera window to safely exit.")
    send_status_to_backend_async({
        "driver_id": args.driver_id,
        "vehicle_id": args.vehicle_id,
        "status": "Attentive",
        "monitoring_state": "Monitoring running normally"
    })

    temporal_tracker = TemporalEvidenceTracker(window_seconds=120.0, min_valid_frames=30)
    frame_count = 0
    prev_eyes_closed = False
    prev_mouth_open = False
    prev_live_status = None
    try:
        while True:
            success, frame = camera_manager.read()
            if not success or frame is None:
                if camera_manager.consecutive_failures >= camera_manager.max_consecutive_failures:
                    logger.error("Camera stream disconnected or terminated. Ending monitoring loop.")
                    break
                continue

            frame_count += 1
            if args.max_frames and frame_count >= args.max_frames:
                logger.info(f"Reached configured limit of {args.max_frames} frames. Stopping.")
                break

            # A. Phone Detection (YOLO - Optional)
            phone_detected, phone_conf, detected_boxes = phone_detector.detect(frame)

            # B. Face Landmark Detection (MediaPipe)
            face_detected, avg_ear, mouth_mar, landmarks = face_detector.process_frame(frame)

            # C. Behaviour State Evaluation with Elapsed Time
            drowsy_info = drowsiness_detector.update(avg_ear)
            yawn_info = yawn_detector.update(mouth_mar)
            posture_info = posture_detector.update(landmarks, frame.shape)

            # Raw conditions for event persistence tracking
            is_eye_closed = drowsiness_detector.is_eye_closed(avg_ear)
            is_mouth_open = yawn_detector.is_mouth_open(mouth_mar)
            is_head_down = posture_info.get("is_unhealthy_posture", False)
            posture_state = posture_info.get("posture_state", "UPRIGHT")
            posture_metrics = posture_info.get("metrics", {})

            # Ingest frame into rolling temporal evidence tracker
            temporal_summary = temporal_tracker.update(
                face_detected=face_detected,
                is_eye_closed=is_eye_closed,
                ear=avg_ear,
                posture_state=posture_state
            )

            # Diagnostic logging: periodic heartbeat every 30 frames (~1.0s)
            if frame_count % 30 == 0:
                phone_state_tag = "DETECTED" if phone_detected else ("CLEAR" if phone_detector.is_available else "UNAVAILABLE")
                if face_detected and avg_ear is not None:
                    logger.info(
                        f"[TRACKING HEARTBEAT] Face: DETECTED | EAR: {avg_ear:.3f} | "
                        f"Eyes: {'CLOSED' if is_eye_closed else 'OPEN'} | MAR: {mouth_mar:.2f} | "
                        f"Mouth: {'OPEN' if is_mouth_open else 'CLOSED'} | "
                        f"Pose: {posture_state} | Phone: {phone_state_tag} | "
                        f"Alarm: {'ACTIVE' if alarm_manager.alarm_on else 'SILENT'}"
                    )
                else:
                    logger.info(
                        f"[TRACKING HEARTBEAT] Face: NOT DETECTED | Searching for driver... | Phone: {phone_state_tag}"
                    )

            # Real-time driver action classification
            cur_act = event_manager.get_current_active_event_type()
            if cur_act == "DROWSINESS":
                live_label = "Drowsy"
            elif cur_act == "YAWNING":
                live_label = "Yawning"
            elif cur_act == "PHONE_DETECTED":
                live_label = "Phone detected"
            elif cur_act == "HEAD_DOWN":
                live_label = "Head down"
            elif is_eye_closed:
                live_label = "Eyes closed"
            elif is_mouth_open:
                live_label = "Mouth open"
            elif phone_detected:
                live_label = "Phone visible"
            elif is_head_down:
                live_label = "Head slumped"
            elif face_detected:
                live_label = "Attentive"
            else:
                live_label = "Searching for driver"

            # Dispatch status immediately whenever driver action changes OR on 30-frame heartbeat (~1.0s)
            action_changed = (live_label != prev_live_status)
            heartbeat_due = (frame_count % 30 == 0)

            if action_changed or heartbeat_due:
                prev_live_status = live_label
                send_status_to_backend_async({
                    "driver_id": args.driver_id,
                    "vehicle_id": args.vehicle_id,
                    "status": live_label,
                    "monitoring_state": "Monitoring running normally",
                    "metrics": {
                        "ear": round(avg_ear, 3) if avg_ear is not None else None,
                        "mar": round(mouth_mar, 2) if mouth_mar is not None else None,
                        "phone_detected": phone_detected,
                        "posture": posture_state,
                        "temporal": temporal_summary
                    }
                })

            # Diagnostic logging: phone detection
            if phone_detected:
                conf_pct = f"{phone_conf * 100:.0f}%" if phone_conf is not None else "N/A"
                logger.warning(
                    f"[PHONE DETECTED] Mobile phone visible in frame (Confidence: {conf_pct}) | Tracking usage duration..."
                )

            # Diagnostic logging: posture & head down / lay down
            if is_head_down:
                pose_dur = posture_info.get("duration", 0.0)
                logger.warning(
                    f"[UNSAFE POSTURE] Driver posture: {posture_state} | "
                    f"Duration: {pose_dur:.2f}s / {posture_detector.duration_threshold}s"
                )
                if posture_info.get("is_head_down"):
                    logger.warning(
                        f"[POSTURE THRESHOLD CROSSED] Driver laying down / head down {pose_dur:.2f}s >= threshold! Triggering Event & Local Alarm..."
                    )

            # Diagnostic logging: eye closure state changes & threshold crossings
            ear_val_str = f"{avg_ear:.3f}" if avg_ear is not None else "N/A"
            if is_eye_closed:
                closure_dur = drowsy_info.get("duration", 0.0)
                logger.warning(
                    f"[EYE CLOSURE] Eyes CLOSED | Current EAR: {ear_val_str} < {args.ear_threshold:.2f} | "
                    f"Closure Duration: {closure_dur:.2f}s / {drowsiness_detector.duration_threshold}s"
                )
                if drowsy_info.get("is_drowsy"):
                    logger.warning(
                        f"[DROWSINESS THRESHOLD CROSSED] Eye closure duration {closure_dur:.2f}s >= {drowsiness_detector.duration_threshold}s! Triggering Event & Local Alarm..."
                    )
            elif prev_eyes_closed:
                logger.info(
                    f"[EYES REOPENED] Driver eyes open | EAR: {ear_val_str} >= {args.ear_threshold:.2f} | Resetting closure duration."
                )

            prev_eyes_closed = is_eye_closed

            # Diagnostic logging: mouth open & yawning state changes & threshold crossings
            mar_val_str = f"{mouth_mar:.2f}" if mouth_mar is not None else "N/A"
            if is_mouth_open:
                yawn_dur = yawn_info.get("duration", 0.0)
                logger.warning(
                    f"[MOUTH OPEN] Driver mouth open | Current MAR: {mar_val_str} >= {args.mar_threshold:.2f} | "
                    f"Open Duration: {yawn_dur:.2f}s / {yawn_detector.duration_threshold:.1f}s"
                )
                if yawn_info.get("is_yawning"):
                    logger.warning(
                        f"[YAWNING THRESHOLD CROSSED] Mouth open duration {yawn_dur:.2f}s >= {yawn_detector.duration_threshold:.1f}s! Triggering Event & Local Alarm..."
                    )
            elif prev_mouth_open:
                logger.info(
                    f"[MOUTH CLOSED] Driver mouth closed | MAR: {mar_val_str} < {args.mar_threshold:.2f} | Resetting open duration."
                )

            prev_mouth_open = is_mouth_open

            # D. Centralized Event Lifecycle & Persistence
            active_events = event_manager.process_frame_states(
                is_eye_closed=is_eye_closed,
                is_mouth_open=is_mouth_open,
                is_phone_detected=phone_detected,
                is_head_down=is_head_down,
                current_ear=avg_ear,
                mouth_dist=mouth_mar,
                phone_conf=phone_conf,
                posture_metrics=posture_metrics
            )

            # E. Compute Overall Severity
            current_event = event_manager.get_current_active_event_type()
            overall_severity = "SAFE"
            if current_event and current_event in active_events:
                overall_severity = active_events[current_event].get("severity", "SAFE")
            elif active_events:
                # If any active event is critical
                if any(v.get("severity") == "CRITICAL" for v in active_events.values()):
                    overall_severity = "CRITICAL"
                elif any(v.get("severity") == "WARNING" for v in active_events.values()):
                    overall_severity = "WARNING"

            # F. Audio Alarm Control
            alarm_manager.update(event_manager.is_unsafe_active, severity=overall_severity)

            # G. HUD Visualization (if GUI display enabled)
            if not args.headless:
                if not phone_detector.enabled:
                    phone_status_str = "DISABLED"
                elif not phone_detector.is_available:
                    phone_status_str = "UNAVAILABLE"
                elif phone_detected:
                    phone_status_str = "DETECTED"
                else:
                    phone_status_str = "CLEAR"

                HUDVisualizer.draw_phone_boxes(frame, detected_boxes)
                HUDVisualizer.draw_hud(
                    frame=frame,
                    face_detected=face_detected,
                    ear=avg_ear,
                    mouth_mar=mouth_mar,
                    is_phone_detected=phone_detected,
                    phone_status=phone_status_str,
                    active_events=active_events,
                    overall_severity=overall_severity,
                    current_event_type=current_event,
                    posture_state=posture_state,
                    posture_metrics=posture_metrics
                )

                cv2.imshow("AI Driver Safety Monitoring Service", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    logger.info("User requested shutdown ('q' key pressed).")
                    break

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Stopping monitoring service...")
    except Exception as e:
        logger.error(f"Unexpected error in monitoring loop: {e}", exc_info=True)
    finally:
        # Graceful Resource Cleanup
        logger.info("Initiating service shutdown and cleanup...")
        event_manager.flush_active_events()
        alarm_manager.stop()
        face_detector.close()
        camera_manager.release()
        session.close()

        send_status_to_backend_async({
            "driver_id": args.driver_id,
            "vehicle_id": args.vehicle_id,
            "status": "OFF_DUTY",
            "monitoring_state": "Camera not started"
        })

        if not args.headless:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

        summary = session.get_summary()
        logger.info("=" * 60)
        logger.info(f"DRIVING SESSION SUMMARY ({summary['session_id']}):")
        logger.info(f"  Duration:         {summary['duration_seconds']}s")
        logger.info(f"  Drowsiness Events:{summary['drowsiness_count']}")
        logger.info(f"  Yawning Events:   {summary['yawning_count']}")
        logger.info(f"  Phone Use Events: {summary['phone_count']}")
        logger.info(f"  Head Down Events: {summary.get('head_down_count', 0)}")
        logger.info(f"  Warning Events:   {summary['warning_count']}")
        logger.info(f"  Critical Events:  {summary['critical_count']}")
        logger.info("=" * 60)
        logger.info("Driver monitoring service safely stopped.")


if __name__ == "__main__":
    main()

