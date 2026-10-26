import cv2

class HUDVisualizer:
    """Renders real-time HUD overlays, bounding boxes, and metrics on video frames."""

    @staticmethod
    def draw_phone_boxes(frame, detected_boxes):
        """Draws bounding boxes and labels for detected mobile phones."""
        for (x1, y1, x2, y2, conf) in detected_boxes:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
            cv2.putText(
                frame,
                f"PHONE DETECTED! {conf:.2f}",
                (x1, max(y1 - 10, 30)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

    @staticmethod
    def draw_hud(
        frame,
        ear: float,
        mouth_dist: float,
        is_phone_detected: bool,
        is_drowsy_detected: bool,
        is_yawning_detected: bool,
        current_event_type: str,
        overall_severity: str
    ):
        """Draws structured vehicle monitoring HUD overlay."""
        h, w, _ = frame.shape

        # Header Title Banner
        cv2.rectangle(frame, (0, 0), (w, 35), (30, 30, 30), -1)
        cv2.putText(
            frame,
            "AI FLEET DRIVER BEHAVIOUR & SAFETY MONITOR",
            (15, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        # Left Column Metrics (EAR and MAR)
        ear_str = f"EAR: {ear:.2f}" if ear is not None else "EAR: N/A"
        mouth_str = f"MAR: {mouth_dist:.2f}" if mouth_dist is not None else "MAR: N/A"

        cv2.putText(frame, ear_str, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, mouth_str, (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 165, 0), 2)

        # Right Column States
        phone_txt = "YES" if is_phone_detected else "NO"
        yawn_txt = "YES" if is_yawning_detected else "NO"
        drowsy_txt = "YES" if is_drowsy_detected else "NO"

        cv2.putText(frame, f"Phone: {phone_txt}", (w - 180, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(frame, f"Yawn: {yawn_txt}", (w - 180, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(frame, f"Drowsy: {drowsy_txt}", (w - 180, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        # On-screen active alert banner if active
        if is_phone_detected:
            cv2.putText(frame, "WARNING: PHONE USE!", (100, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)
        if is_drowsy_detected:
            cv2.putText(frame, "DROWSINESS DETECTED!", (100, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)
        if is_yawning_detected:
            cv2.putText(frame, "YAWNING DETECTED!", (100, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 255), 3)

        # Bottom Driver Status Banner
        banner_color = (0, 255, 0) # Green for SAFE
        if overall_severity == "WARNING":
            banner_color = (0, 165, 255) # Orange
        elif overall_severity == "CRITICAL":
            banner_color = (0, 0, 255) # Red

        event_name = current_event_type or "NONE"
        status_line = f"STATUS: {overall_severity} | EVENT: {event_name}"

        cv2.rectangle(frame, (0, h - 45), (w, h), (20, 20, 20), -1)
        cv2.putText(
            frame,
            status_line,
            (20, h - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            banner_color,
            2
        )
