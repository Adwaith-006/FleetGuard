import math
import cv2
import mediapipe as mp
from config.settings import (
    LEFT_EYE_LANDMARKS,
    RIGHT_EYE_LANDMARKS,
    UPPER_LIP_LANDMARK,
    LOWER_LIP_LANDMARK,
    MOUTH_LEFT_CORNER,
    MOUTH_RIGHT_CORNER
)

def euclidean_distance(point1, point2):
    return math.sqrt(
        (point1[0] - point2[0]) ** 2 +
        (point1[1] - point2[1]) ** 2
    )

def eye_aspect_ratio(landmarks, eye_indices, w, h):
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
    bottom1 = (int(p5.x * w), int(p5.y * h))
    bottom2 = (int(p6.x * w), int(p6.y * h))

    horizontal = euclidean_distance(left, right)
    if horizontal == 0:
        return 0.0

    vertical = (
        euclidean_distance(top1, bottom1) +
        euclidean_distance(top2, bottom2)
    ) / 2.0

    return vertical / horizontal

def mouth_ratio(landmarks, w, h):
    """Calculates normalized Mouth Aspect Ratio (MAR) = vertical_height / horizontal_width."""
    upper = landmarks[UPPER_LIP_LANDMARK]
    lower = landmarks[LOWER_LIP_LANDMARK]
    left = landmarks[MOUTH_LEFT_CORNER]
    right = landmarks[MOUTH_RIGHT_CORNER]

    upper_point = (int(upper.x * w), int(upper.y * h))
    lower_point = (int(lower.x * w), int(lower.y * h))
    left_point = (int(left.x * w), int(left.y * h))
    right_point = (int(right.x * w), int(right.y * h))

    vertical = euclidean_distance(upper_point, lower_point)
    horizontal = euclidean_distance(left_point, right_point)

    if horizontal == 0:
        return 0.0

    return vertical / horizontal


class FaceMeshDetector:
    """Wraps MediaPipe Face Mesh processing and extracts EAR and Mouth Opening metrics."""

    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True
        )

    def process_frame(self, frame):
        """
        Processes a BGR image frame.
        Returns:
            face_detected (bool),
            avg_ear (float or None),
            mouth_open (float or None),
            landmarks (list or None)
        """
        h, w, _ = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)

        if not results.multi_face_landmarks:
            return False, None, None, None

        face_landmarks = results.multi_face_landmarks[0]
        landmarks = face_landmarks.landmark

        left_ear = eye_aspect_ratio(landmarks, LEFT_EYE_LANDMARKS, w, h)
        right_ear = eye_aspect_ratio(landmarks, RIGHT_EYE_LANDMARKS, w, h)
        avg_ear = (left_ear + right_ear) / 2.0

        mouth_open = mouth_ratio(landmarks, w, h)

        return True, avg_ear, mouth_open, landmarks

    def close(self):
        self.face_mesh.close()
