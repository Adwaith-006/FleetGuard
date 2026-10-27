import argparse
import sys
import cv2
from typing import Optional

from config.settings import (
    VIDEO_SOURCE,
    DRIVER_ID,
    VEHICLE_ID,
    ALARM_ENABLED,
    ENABLE_PHONE_DETECTION
)
from utils.logger import logger
from utils.camera_manager import CameraManager
from utils.visualizer import HUDVisualizer
from detection.face_detector import FaceMeshDetector
from detection.phone_detector import PhoneDetector
from detection.drowsiness_detector import DrowsinessDetector
from detection.yawn_detector import YawnDetector
from monitoring.event_manager import EventManager
from monitoring.session_manager import DrivingSession
from alerts.alarm_manager import AlarmManager


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
        "--headless",
        action="store_true",
        help="Run without displaying OpenCV GUI window"
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    logger.info("=" * 60)
    logger.info("AI FLEET DRIVER BEHAVIOUR & SAFETY MONITORING SERVICE")
    logger.info(f"Driver ID: {args.driver_id} | Vehicle ID: {args.vehicle_id} | Source: {args.source}")
    logger.info("=" * 60)

    # 1. Initialize Managers and Detectors
    session = DrivingSession(driver_id=args.driver_id, vehicle_id=args.vehicle_id)
    event_manager = EventManager(session=session, driver_id=args.driver_id, vehicle_id=args.vehicle_id)
    
    alarm_enabled = ALARM_ENABLED and not args.no_alarm
    alarm_manager = AlarmManager(enabled=alarm_enabled)

    face_detector = FaceMeshDetector()
    drowsiness_detector = DrowsinessDetector()
    yawn_detector = YawnDetector()

    phone_detection_enabled = ENABLE_PHONE_DETECTION and not args.no_phone
    phone_detector = PhoneDetector(enabled=phone_detection_enabled)

    logger.info(f"Driving Session ID: {session.session_id}")
    logger.info(f"Face Mesh: {'Available' if face_detector.is_available else 'Unavailable (Disabled)'}")
    logger.info(f"Phone Detection: {'Active' if phone_detector.is_available else phone_detector.status_reason}")
    logger.info(f"Audio Alarm: {'Enabled' if alarm_enabled else 'Disabled'}")

    # 2. Initialize Camera Capture
    camera_manager = CameraManager(source=args.source)
    opened, err = camera_manager.start()
    if not opened:
        logger.error(f"Cannot initialize camera or video source: {err}")
        sys.exit(1)

    logger.info("Monitoring active. Press 'q' in the camera window to safely exit.")

    try:
        while True:
            success, frame = camera_manager.read()
            if not success or frame is None:
                if camera_manager.consecutive_failures >= camera_manager.max_consecutive_failures:
                    logger.error("Camera stream disconnected or terminated. Ending monitoring loop.")
                    break
                continue

            # A. Phone Detection (YOLO - Optional)
            phone_detected, phone_conf, detected_boxes = phone_detector.detect(frame)

            # B. Face Landmark Detection (MediaPipe)
            face_detected, avg_ear, mouth_mar, landmarks = face_detector.process_frame(frame)

            # C. Behaviour State Evaluation with Elapsed Time
            drowsy_info = drowsiness_detector.update(avg_ear)
            yawn_info = yawn_detector.update(mouth_mar)

            # Raw conditions for event persistence tracking
            is_eye_closed = drowsiness_detector.is_eye_closed(avg_ear)
            is_mouth_open = yawn_detector.is_mouth_open(mouth_mar)

            # D. Centralized Event Lifecycle & Persistence
            active_events = event_manager.process_frame_states(
                is_eye_closed=is_eye_closed,
                is_mouth_open=is_mouth_open,
                is_phone_detected=phone_detected,
                current_ear=avg_ear,
                mouth_dist=mouth_mar,
                phone_conf=phone_conf
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
                phone_status_str = "ACTIVE" if phone_detected else ("READY" if phone_detector.is_available else "OFF")
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
                    current_event_type=current_event
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
        logger.info(f"  Warning Events:   {summary['warning_count']}")
        logger.info(f"  Critical Events:  {summary['critical_count']}")
        logger.info("=" * 60)
        logger.info("Driver monitoring service safely stopped.")


if __name__ == "__main__":
    main()


