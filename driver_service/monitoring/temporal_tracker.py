"""
Temporal Evidence Tracker for Driver Monitoring Service.
Maintains a rolling time-window buffer of frame-level observations
to calculate drowsiness ratio, consecutive eye closures, and face visibility quality.
"""

from collections import deque
from datetime import datetime, timezone
import time
from typing import Dict, Any, Optional


class TemporalEvidenceTracker:
    """
    Maintains a rolling temporal window (default 120s) of camera observations.
    Calculates:
      drowsiness_ratio = closed_eye_frames / valid_face_visible_frames
    Tracks consecutive eye closure duration and face visibility quality.
    Does NOT count missing-face frames as closed-eye frames.
    """

    def __init__(self, window_seconds: float = 120.0, min_valid_frames: int = 30):
        self.window_seconds = float(window_seconds)
        self.min_valid_frames = int(min_valid_frames)
        # deque items: (timestamp_float, face_detected, is_eye_closed, ear, posture_state)
        self.buffer = deque()
        self.consecutive_closed_start: Optional[float] = None
        self.last_consecutive_closed_sec: float = 0.0

    def update(
        self,
        face_detected: bool,
        is_eye_closed: bool,
        ear: Optional[float] = None,
        posture_state: str = "UPRIGHT",
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Ingests a single frame's observation into the rolling window.
        """
        now = timestamp if timestamp is not None else time.time()

        # Update consecutive closed duration (only when face is visible)
        if face_detected and is_eye_closed:
            if self.consecutive_closed_start is None:
                self.consecutive_closed_start = now
            self.last_consecutive_closed_sec = max(0.0, now - self.consecutive_closed_start)
        else:
            self.consecutive_closed_start = None
            self.last_consecutive_closed_sec = 0.0

        # Ingest into rolling buffer
        self.buffer.append((now, face_detected, is_eye_closed, ear, posture_state))

        # Evict old observations outside the rolling window
        cutoff = now - self.window_seconds
        while self.buffer and self.buffer[0][0] < cutoff:
            self.buffer.popleft()

        return self.get_summary(now)

    def get_summary(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        """
        Calculates and returns rolling temporal metrics.
        """
        total_frames = len(self.buffer)
        valid_face_frames = sum(1 for _, face, _, _, _ in self.buffer if face)
        closed_eye_frames = sum(1 for _, face, closed, _, _ in self.buffer if face and closed)

        data_quality_ok = valid_face_frames >= self.min_valid_frames

        if data_quality_ok and valid_face_frames > 0:
            drowsiness_ratio = round(closed_eye_frames / valid_face_frames, 3)
        else:
            drowsiness_ratio = 0.0

        face_visible_ratio = round(valid_face_frames / total_frames, 2) if total_frames > 0 else 0.0

        return {
            "window_seconds": self.window_seconds,
            "total_frames": total_frames,
            "valid_face_frames": valid_face_frames,
            "closed_eye_frames": closed_eye_frames,
            "drowsiness_ratio": drowsiness_ratio,
            "consecutive_closed_sec": round(self.last_consecutive_closed_sec, 2),
            "face_visible_ratio": face_visible_ratio,
            "data_quality_ok": data_quality_ok
        }

    def reset(self):
        """Resets the rolling buffer."""
        self.buffer.clear()
        self.consecutive_closed_start = None
        self.last_consecutive_closed_sec = 0.0
