from config.settings import EAR_THRESHOLD

class DrowsinessDetector:
    """Evaluates raw EAR value against configured EAR threshold."""

    def __init__(self, threshold=EAR_THRESHOLD):
        self.threshold = threshold

    def is_eye_closed(self, ear):
        """Returns True if EAR is below threshold (eyes closed)."""
        if ear is None:
            return False
        return ear < self.threshold
