from config.settings import (
    DROWSINESS_DURATION_THRESHOLD,
    YAWN_MIN_DURATION,
    PHONE_DURATION_THRESHOLD,
    HEAD_DOWN_DURATION_THRESHOLD
)


class SeverityManager:
    """
    Evaluates and assigns severity levels (SAFE, LOW, WARNING, CRITICAL)
    and operational status codes for driver behavioural safety events.
    """

    @staticmethod
    def evaluate_severity(event_type: str, duration: float, confidence: float = None) -> str:
        """
        Determines severity level based on event type, duration, and optional confidence.
        """
        evt = (event_type or "").upper()

        if evt == "DROWSINESS":
            if duration >= 3.0:
                return "CRITICAL"
            elif duration >= DROWSINESS_DURATION_THRESHOLD:
                return "WARNING"
            return "SAFE"

        elif evt == "YAWNING":
            if duration >= 4.0:
                return "CRITICAL"
            elif duration >= YAWN_MIN_DURATION:
                return "WARNING"
            return "SAFE"

        elif "PHONE" in evt:
            if duration >= 4.0:
                return "CRITICAL"
            elif duration >= PHONE_DURATION_THRESHOLD:
                return "WARNING"
            return "LOW"

        elif "HEAD" in evt or "POSTURE" in evt or "LAY" in evt:
            if duration >= 3.0:
                return "CRITICAL"
            elif duration >= HEAD_DOWN_DURATION_THRESHOLD:
                return "WARNING"
            return "SAFE"

        return "SAFE"

    @staticmethod
    def classify_status(event_type: str, duration: float, severity: str = "WARNING") -> str:
        """
        Assigns an objective operational status string matching backend classification schema.
        """
        evt = (event_type or "").upper()

        if severity == "CRITICAL":
            return "HIGH_RISK" if (evt == "DROWSINESS" or "HEAD" in evt) else "UNSAFE"

        if evt == "DROWSINESS":
            return "DROWSINESS_DETECTED" if duration >= DROWSINESS_DURATION_THRESHOLD else "OBSERVED"
        elif evt == "YAWNING":
            return "ATTENTION_REQUIRED" if duration >= YAWN_MIN_DURATION else "OBSERVED"
        elif "PHONE" in evt:
            return "ATTENTION_REQUIRED" if duration >= PHONE_DURATION_THRESHOLD else "BRIEF"
        elif "HEAD" in evt or "POSTURE" in evt or "LAY" in evt:
            return "UNSAFE_POSTURE" if duration >= HEAD_DOWN_DURATION_THRESHOLD else "OBSERVED"

        return "OBSERVED"


