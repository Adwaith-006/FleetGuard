import math
import time
from typing import Optional, Dict, Any, Tuple

import cv2
import numpy as np

from config.settings import (
    ENABLE_POSTURE_DETECTION,
    HEAD_DOWN_DURATION_THRESHOLD,
    HEAD_DOWN_COOLDOWN,
    HEAD_PITCH_DOWN_THRESHOLD,
    HEAD_ROLL_THRESHOLD,
    HEAD_SLUMP_Y_THRESHOLD,
    FOREHEAD_LANDMARK,
    NOSE_TIP_LANDMARK,
    CHIN_LANDMARK,
)
from utils.logger import logger


class PostureDetector:
    STATE_UPRIGHT = "UPRIGHT"
    STATE_HEAD_DOWN = "HEAD_DOWN"
    STATE_LAYING_SIDEWAYS = "LAYING_SIDEWAYS"
    STATE_SLUMP_DOWN = "SLUMP_DOWN"

    FACE_MODEL_3D = np.array(
        [
            (0.0, 0.0, 0.0),
            (0.0, -330.0, -65.0),
            (-225.0, 170.0, -135.0),
            (225.0, 170.0, -135.0),
            (-150.0, -150.0, -125.0),
            (150.0, -150.0, -125.0),
        ],
        dtype=np.float64,
    )

    def __init__(
        self,
        enabled: bool = ENABLE_POSTURE_DETECTION,
        duration_threshold: float = HEAD_DOWN_DURATION_THRESHOLD,
        cooldown: float = HEAD_DOWN_COOLDOWN,
        pitch_threshold: float = HEAD_PITCH_DOWN_THRESHOLD,
        roll_threshold: float = HEAD_ROLL_THRESHOLD,
        slump_y_threshold: float = HEAD_SLUMP_Y_THRESHOLD,
        missing_face_tolerance: float = 0.35,
    ):
        self.enabled = enabled
        self.duration_threshold = duration_threshold
        self.cooldown = cooldown
        self.pitch_threshold = pitch_threshold
        self.roll_threshold = roll_threshold
        self.slump_y_threshold = slump_y_threshold
        self.missing_face_tolerance = missing_face_tolerance

        self.posture_start_time: Optional[float] = None
        self.last_unsafe_time: Optional[float] = None
        self.last_event_time: Optional[float] = None
        self.last_face_seen_time: Optional[float] = None

        self.current_state = self.STATE_UPRIGHT
        self.active_posture_type = self.STATE_UPRIGHT

    @staticmethod
    def _get_coords(landmark_item, w: int, h: int):
        """Return normalized facial landmark coordinates."""

        if hasattr(landmark_item, "x") and hasattr(landmark_item, "y"):
            return float(landmark_item.x), float(landmark_item.y)

        if isinstance(landmark_item, (tuple, list)) and len(landmark_item) >= 2:
            x, y = float(landmark_item[0]), float(landmark_item[1])

            if x > 1.0 or y > 1.0:
                return x / max(w, 1), y / max(h, 1)

            return x, y

        raise ValueError("Invalid facial landmark coordinates")

    @staticmethod
    def _normalize_pitch(raw_pitch: float) -> float:
        """Normalize an angle to [-90, 90)."""
        return (float(raw_pitch) + 90.0) % 180.0 - 90.0

    def evaluate_posture(
        self,
        landmarks: Any,
        frame_shape: Tuple[int, int] = (480, 640),
    ):
        if landmarks is None or not self.enabled:
            return False, self.STATE_UPRIGHT, {}

        h, w = frame_shape[:2]
        h = max(h, 1)
        w = max(w, 1)

        try:
            _, forehead_y = self._get_coords(
                landmarks[FOREHEAD_LANDMARK], w, h
            )
            nose_x, nose_y = self._get_coords(
                landmarks[NOSE_TIP_LANDMARK], w, h
            )
            chin_x, chin_y = self._get_coords(
                landmarks[CHIN_LANDMARK], w, h
            )

            left_eye_x, left_eye_y = self._get_coords(
                landmarks[33], w, h
            )
            right_eye_x, right_eye_y = self._get_coords(
                landmarks[263], w, h
            )

            left_mouth_x, left_mouth_y = self._get_coords(
                landmarks[61], w, h
            )
            right_mouth_x, right_mouth_y = self._get_coords(
                landmarks[291], w, h
            )

            # Calculate head roll from the eye line.
            dx = (right_eye_x - left_eye_x) * w
            dy = (right_eye_y - left_eye_y) * h
            roll_deg = math.degrees(math.atan2(dy, dx))

            # Calculate facial vertical ratio.
            d_top = nose_y - forehead_y
            d_bottom = chin_y - nose_y

            if d_top > 0.001 and d_bottom >= 0:
                ratio = d_bottom / d_top
            else:
                ratio = float("inf")

            # Calculate 3D head pose.
            pitch_deg = 0.0
            yaw_deg = 0.0
            pitch_valid = False

            try:
                image_points = np.array(
                    [
                        (nose_x * w, nose_y * h),
                        (chin_x * w, chin_y * h),
                        (left_eye_x * w, left_eye_y * h),
                        (right_eye_x * w, right_eye_y * h),
                        (left_mouth_x * w, left_mouth_y * h),
                        (right_mouth_x * w, right_mouth_y * h),
                    ],
                    dtype=np.float64,
                )

                focal_length = float(w)

                camera_matrix = np.array(
                    [
                        [focal_length, 0.0, w / 2.0],
                        [0.0, focal_length, h / 2.0],
                        [0.0, 0.0, 1.0],
                    ],
                    dtype=np.float64,
                )

                dist_coeffs = np.zeros((4, 1), dtype=np.float64)

                success, rvec, _ = cv2.solvePnP(
                    self.FACE_MODEL_3D,
                    image_points,
                    camera_matrix,
                    dist_coeffs,
                    flags=cv2.SOLVEPNP_ITERATIVE,
                )

                if success:
                    rmat, _ = cv2.Rodrigues(rvec)
                    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

                    raw_pitch = float(angles[0])
                    pitch_deg = self._normalize_pitch(raw_pitch)
                    yaw_deg = float(angles[1])

                    pitch_valid = (
                        np.isfinite(pitch_deg)
                        and np.isfinite(yaw_deg)
                    )

            except (cv2.error, ValueError, TypeError, IndexError) as exc:
                logger.debug("PnP calculation failed: %s", exc)

            metrics = {
                "roll": round(float(roll_deg), 1),
                "pitch": round(float(pitch_deg), 1),
                "yaw": round(float(yaw_deg), 1),
                "ratio": round(float(ratio), 2) if np.isfinite(ratio) else None,
                "nose_y": round(float(nose_y), 2),
                "pitch_valid": bool(pitch_valid),
            }

            logger.debug(
                "Posture | Pitch: %.1f | Roll: %.1f | Ratio: %s",
                pitch_deg,
                roll_deg,
                metrics["ratio"],
            )

            # 1. Sideways head tilt.
            if abs(roll_deg) >= self.roll_threshold:
                return True, self.STATE_LAYING_SIDEWAYS, metrics

            # 2. Head-down detection.
            ratio_head_down = (
                np.isfinite(ratio) and ratio <= 0.48
            )

            pitch_head_down = (
                pitch_valid
                and pitch_deg <= self.pitch_threshold
            )

            if ratio_head_down or pitch_head_down:
                return True, self.STATE_HEAD_DOWN, metrics

            # 3. Vertical slump detection.
            if nose_y >= self.slump_y_threshold:
                return True, self.STATE_SLUMP_DOWN, metrics

            return False, self.STATE_UPRIGHT, metrics

        except (
            IndexError,
            KeyError,
            TypeError,
            ValueError,
            ZeroDivisionError,
        ) as exc:
            logger.debug("Posture evaluation failed: %s", exc)
            return False, self.STATE_UPRIGHT, {}

    def update(
        self,
        landmarks: Any,
        frame_shape: Tuple[int, int] = (480, 640),
        current_time: Optional[float] = None,
    ) -> Dict[str, Any]:

        now = current_time if current_time is not None else time.time()

        if landmarks is None:
            if self.last_face_seen_time is None:
                missing_duration = float("inf")
            else:
                missing_duration = now - self.last_face_seen_time

            if missing_duration > self.missing_face_tolerance:
                self._reset_posture_tracking()

            return {
                "is_head_down": False,
                "is_unhealthy_posture": False,
                "duration": 0.0,
                "posture_state": self.STATE_UPRIGHT,
                "metrics": {},
                "in_cooldown": self._is_in_cooldown(now),
            }

        self.last_face_seen_time = now

        is_unsafe, posture_state, metrics = self.evaluate_posture(
            landmarks, frame_shape
        )

        if not is_unsafe:
            self._reset_posture_tracking()

            return {
                "is_head_down": False,
                "is_unhealthy_posture": False,
                "duration": 0.0,
                "posture_state": self.STATE_UPRIGHT,
                "metrics": metrics,
                "in_cooldown": self._is_in_cooldown(now),
            }

        # Start a new timer if the unsafe posture changes.
        if (
            self.posture_start_time is None
            or posture_state != self.active_posture_type
        ):
            self.posture_start_time = now
            self.active_posture_type = posture_state

        self.last_unsafe_time = now
        elapsed = max(0.0, now - self.posture_start_time)
        in_cooldown = self._is_in_cooldown(now)

        confirmed_event = (
            elapsed >= self.duration_threshold
            and not in_cooldown
        )

        self.current_state = posture_state

        return {
            "is_head_down": confirmed_event,
            "is_unhealthy_posture": True,
            "duration": round(elapsed, 2),
            "posture_state": self.current_state,
            "metrics": metrics,
            "in_cooldown": in_cooldown,
        }

    def _reset_posture_tracking(self):
        """Reset the active posture and its timer."""
        self.posture_start_time = None
        self.last_unsafe_time = None
        self.current_state = self.STATE_UPRIGHT
        self.active_posture_type = self.STATE_UPRIGHT

    def trigger_event_cooldown(
        self,
        current_time: Optional[float] = None,
    ):
        now = current_time if current_time is not None else time.time()
        self.last_event_time = now

    def _is_in_cooldown(self, now: float) -> bool:
        if self.last_event_time is None or self.cooldown <= 0:
            return False

        return (now - self.last_event_time) < self.cooldown

    def reset(self):
        """Reset all detector state."""
        self._reset_posture_tracking()
        self.last_event_time = None
        self.last_face_seen_time = None