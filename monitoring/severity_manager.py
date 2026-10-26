class SeverityManager:
    """Evaluates and assigns severity levels (SAFE, WARNING, CRITICAL) for driver events."""

    @staticmethod
    def evaluate_severity(event_type: str, duration: float, confidence: float = None) -> str:
        """
        Determines severity based on event type and duration.
        """
        if event_type == "DROWSINESS":
            if duration >= 3.0:
                return "CRITICAL"
            elif duration >= 1.0:
                return "WARNING"
            return "SAFE"

        elif event_type == "YAWNING":
            if duration >= 4.0:
                return "CRITICAL"
            elif duration >= 1.0:
                return "WARNING"
            return "SAFE"

        elif event_type == "PHONE_DETECTED":
            if duration >= 5.0:
                return "CRITICAL"
            elif duration >= 3.0:
                return "WARNING"
            return "LOW"

        return "SAFE"
