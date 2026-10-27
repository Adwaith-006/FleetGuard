import time
from typing import Optional, Dict, Any
from config.settings import (
    EAR_THRESHOLD,
    DROWSINESS_DURATION_THRESHOLD,
    BLINK_MAX_DURATION,
    DROWSINESS_COOLDOWN
)


class DrowsinessDetector:
    """
    Evaluates Eye Aspect Ratio (EAR) using real elapsed time.
    
    Distinguishes:
    - Normal eye blinks (transient eye closures < BLINK_MAX_DURATION)
    - Sustained eye closure (continuous eye closure >= DROWSINESS_DURATION_THRESHOLD)
    - Face tracking dropouts (safely handled without falsely inferring drowsiness)
    
    Treats results as potential driver fatigue indicators, not definitive medical assessments.
    """

    STATE_OPEN = "OPEN"
    STATE_BLINK = "BLINK"
    STATE_SUSTAINED_CLOSURE = "SUSTAINED_CLOSURE"

    def __init__(
        self,
        threshold: float = EAR_THRESHOLD,
        duration_threshold: float = DROWSINESS_DURATION_THRESHOLD,
        blink_max_duration: float = BLINK_MAX_DURATION,
        cooldown: float = DROWSINESS_COOLDOWN,
        missing_face_tolerance: float = 0.3
    ):
        self.threshold = threshold
        self.duration_threshold = duration_threshold
        self.blink_max_duration = blink_max_duration
        self.cooldown = cooldown
        self.missing_face_tolerance = missing_face_tolerance

        # Internal state tracking
        self.closure_start_time: Optional[float] = None
        self.last_closed_time: Optional[float] = None
        self.last_event_time: Optional[float] = None
        self.last_face_seen_time: Optional[float] = None
        self.current_state: str = self.STATE_OPEN
        self.total_blinks: int = 0

    def is_eye_closed(self, ear: Optional[float]) -> bool:
        """
        Evaluates raw instantaneous eye closure for backward compatibility.
        Returns True only if EAR is present and below threshold.
        """
        if ear is None:
            return False
        return ear < self.threshold

    def update(
        self,
        ear: Optional[float],
        current_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Updates detector state using elapsed time.
        
        Args:
            ear: Current Eye Aspect Ratio value, or None if face is not detected.
            current_time: Epoch timestamp (seconds). Uses time.time() if None.
            
        Returns:
            Dict containing:
                - state: "OPEN", "BLINK", or "SUSTAINED_CLOSURE"
                - is_drowsy: bool (True only if sustained closure threshold exceeded and not in cooldown)
                - is_blink: bool (True during brief closure)
                - duration: float (elapsed seconds eyes have remained closed)
                - ear: current EAR value or None
                - in_cooldown: bool
        """
        now = current_time if current_time is not None else time.time()

        # Handle face tracking loss
        if ear is None:
            if self.last_face_seen_time is not None:
                missing_duration = now - self.last_face_seen_time
                if missing_duration > self.missing_face_tolerance:
                    # Face lost for longer than tolerance - reset closure timer safely
                    self.closure_start_time = None
                    self.current_state = self.STATE_OPEN

            return {
                "state": self.STATE_OPEN,
                "is_drowsy": False,
                "is_blink": False,
                "duration": 0.0,
                "ear": None,
                "in_cooldown": self._is_in_cooldown(now)
            }

        self.last_face_seen_time = now

        # Check instantaneous closure
        eyes_closed = ear < self.threshold

        if eyes_closed:
            if self.closure_start_time is None:
                self.closure_start_time = now

            self.last_closed_time = now
            elapsed = now - self.closure_start_time

            in_cooldown = self._is_in_cooldown(now)

            if elapsed < self.blink_max_duration:
                self.current_state = self.STATE_BLINK
                is_drowsy = False
            elif elapsed >= self.duration_threshold and not in_cooldown:
                self.current_state = self.STATE_SUSTAINED_CLOSURE
                is_drowsy = True
            else:
                # In between blink threshold and duration threshold, or in cooldown
                self.current_state = self.STATE_BLINK
                is_drowsy = False

            return {
                "state": self.current_state,
                "is_drowsy": is_drowsy,
                "is_blink": (self.current_state == self.STATE_BLINK),
                "duration": round(elapsed, 2),
                "ear": ear,
                "in_cooldown": in_cooldown
            }

        else:
            # Eyes are open
            if self.closure_start_time is not None:
                closure_duration = now - self.closure_start_time
                if closure_duration <= self.blink_max_duration:
                    self.total_blinks += 1

            self.closure_start_time = None
            self.current_state = self.STATE_OPEN

            return {
                "state": self.STATE_OPEN,
                "is_drowsy": False,
                "is_blink": False,
                "duration": 0.0,
                "ear": ear,
                "in_cooldown": self._is_in_cooldown(now)
            }

    def trigger_event_cooldown(self, current_time: Optional[float] = None):
        """Marks that a drowsiness event was recorded and starts cooldown."""
        now = current_time if current_time is not None else time.time()
        self.last_event_time = now

    def _is_in_cooldown(self, now: float) -> bool:
        if self.last_event_time is None or self.cooldown <= 0:
            return False
        return (now - self.last_event_time) < self.cooldown

    def reset(self):
        """Resets all internal timers."""
        self.closure_start_time = None
        self.last_closed_time = None
        self.last_event_time = None
        self.last_face_seen_time = None
        self.current_state = self.STATE_OPEN

