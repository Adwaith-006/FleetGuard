import math
import cv2
from typing import Optional, Tuple, Any
from config.settings import (
    LEFT_EYE_LANDMARKS,
    RIGHT_EYE_LANDMARKS,
    UPPER_LIP_LANDMARK,
    LOWER_LIP_LANDMARK,
    MOUTH_LEFT_CORNER,
    MOUTH_RIGHT_CORNER
)
from utils.logger import logger

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    mp = None
    MEDIAPIPE_AVAILABLE = False


def euclidean_distance(point1: Tuple[int, int], point2: Tuple[int, int]) -> float:
    """Calculates 2D Euclidean distance between two pixel coordinates."""
    return math.sqrt(
        (point1[0] - point2[0]) ** 2 +
        (point1[1] - point2[1]) ** 2
    )


def eye_aspect_ratio(landmarks: Any, eye_indices: list, w: int, h: int) -> float:
    """
    Calculates Eye Aspect Ratio (EAR) based on 6 landmark points.
    Formula: EAR = (||p2 - p6|| + ||p3 - p5||) / (2 * ||p1 - p4||)
    """
    try:
        p1 = landmarks[eye_indices[0]]
        p2 = landmarks[eye_indices[1]]
        p3 = landmarks[eye_indices[2]]
        p4 = landmarks[eye_indices[3]]
        p5 = landmarks[eye_indices[4]]
        p6 = landmarks[eye_indices[5]]

        left = (int(p1.x * w), int(p1.y * h))
        top1 = (int(p2.x * w), int(p2.y * h))
        top2 = (int(p3.x * w), int(p3.y * h))
        right = (int(p4.x * w), int(p4.y * h))
        # In canonical 6-point eye landmark geometry:
        # p2 (top-lateral) pairs vertically with p6 (bottom-lateral)
        # p3 (top-medial) pairs vertically with p5 (bottom-medial)
        bottom1 = (int(p6.x * w), int(p6.y * h))
        bottom2 = (int(p5.x * w), int(p5.y * h))

        horizontal = euclidean_distance(left, right)
        if horizontal <= 0.0:
            return 0.0

        vertical = (
            euclidean_distance(top1, bottom1) +
            euclidean_distance(top2, bottom2)
        ) / 2.0

        return vertical / horizontal
    except (IndexError, AttributeError):
        return 0.0


def _extract_point(item: Any, w: int, h: int) -> Tuple[float, float]:
    """Safely extracts (x, y) in pixel space from landmark object, dict, or tuple."""
    if hasattr(item, "x") and hasattr(item, "y"):
        return (float(item.x) * w, float(item.y) * h)
    if isinstance(item, (tuple, list)) and len(item) >= 2:
        x, y = float(item[0]), float(item[1])
        if x <= 1.0 and y <= 1.0:
            return (x * w, y * h)
        return (x, y)
    raise ValueError(f"Invalid landmark representation: {item}")


def mouth_ratio(landmarks: Any, w: int, h: int) -> float:
    """
    Calculates normalized Mouth Aspect Ratio (MAR) = vertical_height / horizontal_width.
    Uses inner lip margins (landmarks 13 and 14) and mouth corners (landmarks 61 and 291).
    """
    try:
        upper_point = _extract_point(landmarks[UPPER_LIP_LANDMARK], w, h)
        lower_point = _extract_point(landmarks[LOWER_LIP_LANDMARK], w, h)
        left_point = _extract_point(landmarks[MOUTH_LEFT_CORNER], w, h)
        right_point = _extract_point(landmarks[MOUTH_RIGHT_CORNER], w, h)

        vertical = euclidean_distance(upper_point, lower_point)
        horizontal = euclidean_distance(left_point, right_point)

        if horizontal <= 0.0:
            return 0.0

        return vertical / horizontal
    except (IndexError, KeyError, AttributeError, ValueError, TypeError):
        return 0.0


class FaceMeshDetector:
    """Wraps MediaPipe Face Mesh processing and extracts EAR and Mouth Opening metrics."""

    def __init__(self, max_num_faces: int = 1, refine_landmarks: bool = True):
        self.is_available = MEDIAPIPE_AVAILABLE
        self.face_mesh = None

        if not self.is_available:
            logger.warning(
                "MediaPipe is not installed. Face mesh and landmark detection will be disabled. "
                "Install with: pip install mediapipe"
            )
            return

        try:
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                max_num_faces=max_num_faces,
                refine_landmarks=refine_landmarks,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe FaceMesh: {e}")
            self.is_available = False

    def process_frame(self, frame) -> Tuple[bool, Optional[float], Optional[float], Optional[Any]]:
        """
        Processes a BGR image frame.
        Returns:
            Tuple: (face_detected, avg_ear, mouth_mar, landmarks)
            If no face is detected or frame is invalid, returns (False, None, None, None).
        """
        if not self.is_available or self.face_mesh is None or frame is None:
            return False, None, None, None

        try:
            h, w = frame.shape[:2]
            if h == 0 or w == 0:
                return False, None, None, None

            # Convert BGR to RGB with writeable=False for performance optimization
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            results = self.face_mesh.process(rgb_frame)

            if not results or not results.multi_face_landmarks:
                return False, None, None, None

            face_landmarks = results.multi_face_landmarks[0]
            landmarks = face_landmarks.landmark

            left_ear = eye_aspect_ratio(landmarks, LEFT_EYE_LANDMARKS, w, h)
            right_ear = eye_aspect_ratio(landmarks, RIGHT_EYE_LANDMARKS, w, h)
            avg_ear = (left_ear + right_ear) / 2.0

            mouth_mar = mouth_ratio(landmarks, w, h)

            return True, avg_ear, mouth_mar, landmarks

        except Exception as e:
            logger.debug(f"Error processing frame in FaceMeshDetector: {e}")
            return False, None, None, None

    def close(self):
        """Safely closes MediaPipe FaceMesh resources."""
        if self.face_mesh is not None:
            try:
                self.face_mesh.close()
            except Exception as e:
                logger.warning(f"Error closing FaceMesh: {e}")
            self.face_mesh = None

