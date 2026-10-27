import cv2
from typing import Optional, List, Tuple, Dict, Any


class HUDVisualizer:
    """
    Renders real-time HUD overlays, bounding boxes, and driver telemetry on video frames.
    
    Guarantees:
    - Clear textual and symbolic status indicators (does not rely on color alone)
    - Anti-flicker: Only shows alert banners for confirmed sustained events, not transient blinks
    - Clean face detection and phone detector status display
    """

    @staticmethod
    def draw_phone_boxes(frame, detected_boxes: List[Tuple[int, int, int, int, float]]):
        """Draws bounding boxes and confidence labels for detected mobile phones."""
        if not detected_boxes or frame is None:
            return

        for (x1, y1, x2, y2, conf) in detected_boxes:
            # Red bounding box with prominent border
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            label = f"PHONE OBJECT ({conf * 100:.0f}%)"
            
            # Label background box for legibility
            cv2.rectangle(frame, (x1, max(y1 - 24, 0)), (x1 + 180, max(y1, 24)), (0, 0, 200), -1)
            cv2.putText(
                frame,
                label,
                (x1 + 4, max(y1 - 6, 18)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

    @staticmethod
    def draw_hud(
        frame,
        face_detected: bool,
        ear: Optional[float],
        mouth_mar: Optional[float],
        is_phone_detected: bool,
        phone_status: str,
        active_events: Dict[str, Any],
        overall_severity: str = "SAFE",
        current_event_type: Optional[str] = None,
        posture_state: str = "UPRIGHT",
        posture_metrics: Optional[Dict[str, Any]] = None
    ):
        """
        Draws structured driver monitoring HUD overlay on the video frame.
        """
        if frame is None:
            return

        h, w = frame.shape[:2]

        # 1. Top Header Banner
        cv2.rectangle(frame, (0, 0), (w, 36), (25, 25, 25), -1)
        cv2.putText(
            frame,
            "AI FLEET DRIVER MONITORING SERVICE",
            (15, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )

        # 2. Face Presence Indicator (Top Right)
        if face_detected:
            face_text = "[FACE: TRACKED]"
            face_color = (0, 230, 0) # Green
        else:
            face_text = "[FACE: NOT DETECTED]"
            face_color = (0, 165, 255) # Orange

        cv2.putText(
            frame,
            face_text,
            (w - 240, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            face_color,
            2
        )

        # 3. Left Telemetry Card (Semi-transparent background)
        ear_str = f"EAR: {ear:.3f}" if ear is not None else "EAR: N/A"
        mar_str = f"MAR: {mouth_mar:.2f}" if mouth_mar is not None else "MAR: N/A"

        cv2.rectangle(frame, (10, 46), (210, 126), (20, 20, 20), -1)
        cv2.rectangle(frame, (10, 46), (210, 126), (60, 60, 60), 1)

        cv2.putText(frame, ear_str, (18, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 0), 2)
        cv2.putText(frame, mar_str, (18, 94), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 180, 0), 2)
        
        # Posture metric summary
        if posture_metrics and "roll" in posture_metrics:
            pose_num = f"Roll: {posture_metrics['roll']:+.0f} | Pitch: {posture_metrics.get('pitch', 0):+.0f}"
            cv2.putText(frame, pose_num, (18, 118), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)

        # 4. Right Status Card
        cv2.rectangle(frame, (w - 230, 46), (w - 10, 126), (20, 20, 20), -1)
        cv2.rectangle(frame, (w - 230, 46), (w - 10, 126), (60, 60, 60), 1)

        # Phone indicator formatting
        if is_phone_detected or phone_status in ("ACTIVE", "DETECTED"):
            phone_col = (0, 0, 255)  # Red
            phone_line = f"Phone: {phone_status}"
        elif phone_status in ("READY", "CLEAR"):
            phone_col = (0, 230, 0)  # Green
            phone_line = f"Phone: {phone_status}"
        elif phone_status in ("UNAVAILABLE", "ERROR", "NO_WEIGHTS"):
            phone_col = (0, 165, 255)  # Orange
            phone_line = f"Phone: {phone_status}"
        else:
            phone_col = (180, 180, 180)  # Gray for DISABLED/OFF
            phone_line = f"Phone: {phone_status}"

        cv2.putText(frame, phone_line, (w - 220, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.48, phone_col, 2 if is_phone_detected else 1)

        # Posture state indicator
        is_unsafe_pose = posture_state not in ("UPRIGHT", "SAFE", "NORMAL")
        pose_col = (0, 0, 255) if is_unsafe_pose else (0, 230, 0)
        cv2.putText(frame, f"Pose: {posture_state}", (w - 220, 94), cv2.FONT_HERSHEY_SIMPLEX, 0.48, pose_col, 2 if is_unsafe_pose else 1)

        active_cond_txt = current_event_type if current_event_type else "None"
        cv2.putText(frame, f"Active: {active_cond_txt}", (w - 220, 118), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 220, 220), 1)

        # 5. On-Screen Warning Banners (ONLY for sustained active events)
        banner_y = 155
        for evt_type, data in active_events.items():
            duration = data.get("duration", 0.0)
            sev = data.get("severity", "WARNING")

            # Choose banner color based on severity
            if sev == "CRITICAL":
                bg_col = (0, 0, 210) # Red
                txt_col = (255, 255, 255)
                prefix = "CRITICAL ALERT"
            else:
                bg_col = (0, 140, 255) # Orange
                txt_col = (0, 0, 0)
                prefix = "CAUTION"

            if evt_type == "HEAD_DOWN":
                detail_label = "DRIVER LAY DOWN / HEAD DOWN"
            elif evt_type == "PHONE_DETECTED":
                detail_label = "MOBILE PHONE USE DETECTED"
            elif evt_type == "DROWSINESS":
                detail_label = "DROWSINESS - EYES CLOSED"
            elif evt_type == "YAWNING":
                detail_label = "FREQUENT YAWNING"
            else:
                detail_label = evt_type

            alert_msg = f"[{prefix}] {detail_label} ({duration:.1f}s)"
            cv2.rectangle(frame, (15, banner_y - 24), (w - 15, banner_y + 8), bg_col, -1)
            cv2.putText(
                frame,
                alert_msg,
                (25, banner_y - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                txt_col,
                2
            )
            banner_y += 38

        # 6. Bottom Master Status Bar
        if overall_severity == "CRITICAL":
            bar_color = (0, 0, 220) # Red
            status_text = f"STATE: CRITICAL UNATTENTIVE | ACTIVE: {current_event_type or 'MULTIPLE'}"
        elif overall_severity == "WARNING":
            bar_color = (0, 140, 255) # Orange
            status_text = f"STATE: WARNING - ATTENTION REQUIRED | ACTIVE: {current_event_type or 'MULTIPLE'}"
        else:
            bar_color = (0, 180, 0) # Green
            status_text = "STATE: NORMAL / ATTENTIVE | SYSTEM ACTIVE"

        cv2.rectangle(frame, (0, h - 40), (w, h), bar_color, -1)
        cv2.putText(
            frame,
            status_text,
            (20, h - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255) if overall_severity != "SAFE" else (0, 0, 0),
            2
        )

