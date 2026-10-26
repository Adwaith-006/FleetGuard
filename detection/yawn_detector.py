from config.settings import YAWN_MAR_THRESHOLD

class YawnDetector:
    """Evaluates normalized Mouth Aspect Ratio (MAR) metric against yawn threshold."""

    def __init__(self, mar_threshold=YAWN_MAR_THRESHOLD):
        self.mar_threshold = mar_threshold

    def is_mouth_open(self, mar):
        """Returns True if Mouth Aspect Ratio (MAR) equals or exceeds the yawn threshold."""
        if mar is None:
            return False
        return mar >= self.mar_threshold
