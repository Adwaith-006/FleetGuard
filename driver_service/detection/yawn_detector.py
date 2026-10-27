import time
from typing import Optional, Dict, Any
from config.settings import (
    YAWN_MAR_THRESHOLD,
    YAWN_MIN_DURATION,
    YAWN_COOLDOWN
)


class YawnDetector:
    """
    Evaluates normalized Mouth Aspect Ratio (MAR) using real elapsed time.
    
    Distinguishes:
    - Normal talking / laughing / smiling (transient mouth opening < YAWN_MIN_DURATION, MAR ~0.15-0.35)
    - True yawning (sustained wide mouth opening >= YAWN_MIN_DURATION, MAR >= YAWN_MAR_THRESHOLD)
    
    Prevents repeated consecutive triggers using configurable cooldowns and clean timer resets.
    """

    STATE_CLOSED = "CLOSED"
    STATE_TALKING = "TALKING"
    STATE_YAWNING = "YAWNING"

    def __init__(
        self,
        mar_threshold: float = YAWN_MAR_THRESHOLD,
        duration_threshold: float = YAWN_MIN_DURATION,
        cooldown: float = YAWN_COOLDOWN,
        missing_face_tolerance: float = 0.35
    ):
        self.mar_threshold = mar_threshold
        self.duration_threshold = duration_threshold
        self.cooldown = cooldown
        self.missing_face_tolerance = missing_face_tolerance

        # Internal state tracking
        self.open_start_time: Optional[float] = None
        self.last_open_time: Optional[float] = None
        self.last_event_time: Optional[float] = None
        self.last_face_seen_time: Optional[float] = None
        self.current_state: str = self.STATE_CLOSED
        self.total_yawns: int = 0

    def is_mouth_open(self, mar: Optional[float]) -> bool:
        """
        Evaluates raw instantaneous mouth opening.
        Returns True only if MAR is present and equals or exceeds threshold.
        """
        if mar is None:
            return False
        return mar >= self.mar_threshold

    def update(
        self,
        mar: Optional[float],
        current_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Updates yawn detector state using elapsed time.
        
        Args:
            mar: Current Mouth Aspect Ratio (height / width), or None if face missing.
            current_time: Epoch timestamp (seconds). Uses time.time() if None.
            
        Returns:
            Dict containing:
                - state: "CLOSED", "TALKING", or "YAWNING"
                - is_yawning: bool (True only if sustained mouth opening threshold exceeded and not in cooldown)
                - duration: float (elapsed seconds mouth has remained wide open)
                - mar: current MAR value or None
                - in_cooldown: bool
                - threshold: float
                - duration_threshold: float
        """
        now = current_time if current_time is not None else time.time()

        if mar is None:
            if self.last_face_seen_time is not None:
                missing_dur = now - self.last_face_seen_time
                if missing_dur > self.missing_face_tolerance:
                    self.open_start_time = None
                    self.current_state = self.STATE_CLOSED
            else:
                self.open_start_time = None
                self.current_state = self.STATE_CLOSED

            return {
                "state": self.STATE_CLOSED,
                "is_yawning": False,
                "duration": 0.0,
                "mar": None,
                "in_cooldown": self._is_in_cooldown(now),
                "threshold": self.mar_threshold,
                "duration_threshold": self.duration_threshold
            }

        self.last_face_seen_time = now
        is_wide_open = mar >= self.mar_threshold
        in_cooldown = self._is_in_cooldown(now)

        if is_wide_open:
            self.last_open_time = now
            if self.open_start_time is None:
                self.open_start_time = now

            elapsed = max(0.0, now - self.open_start_time)

            if elapsed >= self.duration_threshold and not in_cooldown:
                self.current_state = self.STATE_YAWNING
                is_yawning = True
            else:
                self.current_state = self.STATE_TALKING
                is_yawning = False

            return {
                "state": self.current_state,
                "is_yawning": is_yawning,
                "duration": round(elapsed, 2),
                "mar": round(mar, 3),
                "in_cooldown": in_cooldown,
                "threshold": self.mar_threshold,
                "duration_threshold": self.duration_threshold
            }
        else:
            self.open_start_time = None
            self.current_state = self.STATE_CLOSED
            return {
                "state": self.STATE_CLOSED,
                "is_yawning": False,
                "duration": 0.0,
                "mar": round(mar, 3),
                "in_cooldown": in_cooldown,
                "threshold": self.mar_threshold,
                "duration_threshold": self.duration_threshold
            }

    def trigger_event_cooldown(self, current_time: Optional[float] = None):
        """Marks that a yawn event was recorded and starts cooldown."""
        now = current_time if current_time is not None else time.time()
        self.last_event_time = now
        self.open_start_time = None
        self.current_state = self.STATE_CLOSED
        self.total_yawns += 1

    def _is_in_cooldown(self, now: float) -> bool:
        if self.last_event_time is None or self.cooldown <= 0:
            return False
        return (now - self.last_event_time) < self.cooldown

    def reset(self):
        """Resets all internal timers and states."""
        self.open_start_time = None
        self.last_open_time = None
        self.last_event_time = None
        self.last_face_seen_time = None
        self.current_state = self.STATE_CLOSED
