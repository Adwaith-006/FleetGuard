import cv2
import sys
from config.settings import CAMERA_INDEX
from utils.logger import logger
from utils.visualizer import HUDVisualizer
from detection.face_detector import FaceMeshDetector
from detection.phone_detector import PhoneDetector
from detection.drowsiness_detector import DrowsinessDetector
from detection.yawn_detector import YawnDetector
from monitoring.event_manager import EventManager
from monitoring.session_manager import DrivingSession
from alerts.alarm_manager import AlarmManager


def main():
    logger.info("Initializing Vehicle-Side AI Driver Behaviour & Safety Monitoring System...")

    # Initialize Detector & Manager Modules
    try:
        face_detector = FaceMeshDetector()
        phone_detector = PhoneDetector()
        drowsiness_detector = DrowsinessDetector()
        yawn_detector = YawnDetector()
        session = DrivingSession()
        event_manager = EventManager(session=session)
        alarm_manager = AlarmManager()
        logger.info(f"Active Driving Session started: {session.session_id}")
    except Exception as e:
        logger.error(f"Failed to initialize monitoring system modules: {e}")
        sys.exit(1)

    # Initialize Camera Capture
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        logger.error(f"Cannot open camera at index {CAMERA_INDEX}")
        sys.exit(1)

    logger.info("Camera stream started successfully. Monitoring driver...")
    logger.info("Press 'q' in the camera window to safely exit.")

    try:
        while True:
            success, frame = cap.read()
            if not success:
                logger.warning("Failed to grab frame from camera stream.")
                break

            # Horizontal flip for intuitive selfie mirror view
            frame = cv2.flip(frame, 1)

            # 1. Phone Detection (YOLO)
            phone_detected, phone_conf, detected_boxes = phone_detector.detect(frame)

            # 2. Face Landmark Detection (MediaPipe)
            face_detected, avg_ear, mouth_dist, landmarks = face_detector.process_frame(frame)

            # 3. Raw Threshold Evaluations
            is_eye_closed = drowsiness_detector.is_eye_closed(avg_ear)
            is_mouth_open = yawn_detector.is_mouth_open(mouth_dist)
            is_phone_detected = phone_detected

            # 4. Temporal Persistence & Event Management
            active_summary = event_manager.process_frame_states(
                is_eye_closed=is_eye_closed,
                is_mouth_open=is_mouth_open,
                is_phone_detected=is_phone_detected,
                current_ear=avg_ear,
                mouth_dist=mouth_dist,
                phone_conf=phone_conf
            )

            # 5. Local Alarm Control
            alarm_manager.update(event_manager.is_unsafe_active)

            # 6. Evaluate HUD Display Status
            current_event = event_manager.get_current_active_event_type()
            overall_severity = "SAFE"
            if current_event and current_event in active_summary:
                overall_severity = active_summary[current_event]["severity"]

            # 7. Render Visual Overlays
            HUDVisualizer.draw_phone_boxes(frame, detected_boxes)
            HUDVisualizer.draw_hud(
                frame=frame,
                ear=avg_ear,
                mouth_dist=mouth_dist,
                is_phone_detected=is_phone_detected,
                is_drowsy_detected=is_eye_closed,
                is_yawning_detected=is_mouth_open,
                current_event_type=current_event,
                overall_severity=overall_severity
            )

            # Display Window
            cv2.imshow("AI Fleet Driver Monitoring System", frame)

            # Check Quit Signal ('q')
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                logger.info("Quit command received ('q'). Shutting down...")
                break

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error in main execution loop: {e}")
    finally:
        # Resource Cleanup
        logger.info("Cleaning up resources...")
        alarm_manager.stop()
        face_detector.close()
        cap.release()
        cv2.destroyAllWindows()
        summary = session.get_summary()
        logger.info(
            f"Session {session.session_id} ended. Active Duration: {summary.get('duration_seconds')}s | "
            f"Drowsy: {summary.get('drowsiness_count')} | Yawn: {summary.get('yawning_count')} | "
            f"Phone: {summary.get('phone_count')} | Critical: {summary.get('critical_count')}"
        )
        logger.info("Session ended. Vehicle monitor safely stopped.")


if __name__ == "__main__":
    main()