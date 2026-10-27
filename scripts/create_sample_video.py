"""
Utility script to generate a synthetic driver video for offline / prerecorded testing.
Generates simulated facial features (eyes open, closed, mouth wide open) so the pipeline
can be tested end-to-end without needing a physical webcam or live human subject.
"""

import os
import cv2
import numpy as np

def create_synthetic_driver_video(output_path: str = "data/sample_driver.mp4", duration_sec: int = 8, fps: int = 20):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    width, height = 640, 480
    total_frames = duration_sec * fps

    # Use mp4v codec
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    if not out.isOpened():
        # Fallback to XVID
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        output_path = output_path.replace(".mp4", ".avi")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    print(f"Generating synthetic test video at: {output_path} ({duration_sec}s @ {fps}fps)...")

    for frame_idx in range(total_frames):
        # Canvas: dark car interior
        frame = np.full((height, width, 3), (35, 30, 30), dtype=np.uint8)

        # Draw steering wheel bottom arc
        cv2.ellipse(frame, (320, 500), (220, 140), 0, 180, 360, (60, 60, 60), 18)

        # Draw head / face oval
        center_x, center_y = 320, 230
        cv2.ellipse(frame, (center_x, center_y), (95, 125), 0, 0, 360, (180, 205, 235), -1)

        sec = frame_idx / fps

        # State 1: Normal driving (0 - 2.5s)
        # State 2: Drowsiness / eyes closed (2.5 - 5.5s) -> 3.0s duration triggers WARNING then CRITICAL
        # State 3: Yawning / mouth wide open (5.5 - 8.0s) -> 2.5s duration triggers YAWN event
        is_eyes_closed = (2.5 <= sec <= 5.5)
        is_yawning = (5.5 < sec <= 7.8)

        # Draw eyes
        eye_y = center_y - 25
        left_eye_x = center_x - 35
        right_eye_x = center_x + 35

        if is_eyes_closed:
            # Closed eyes (horizontal slits)
            cv2.line(frame, (left_eye_x - 18, eye_y), (left_eye_x + 18, eye_y), (30, 30, 50), 3)
            cv2.line(frame, (right_eye_x - 18, eye_y), (right_eye_x + 18, eye_y), (30, 30, 50), 3)
        else:
            # Open eyes
            cv2.circle(frame, (left_eye_x, eye_y), 12, (255, 255, 255), -1)
            cv2.circle(frame, (left_eye_x, eye_y), 6, (60, 40, 20), -1)
            cv2.circle(frame, (right_eye_x, eye_y), 12, (255, 255, 255), -1)
            cv2.circle(frame, (right_eye_x, eye_y), 6, (60, 40, 20), -1)

        # Draw mouth
        mouth_y = center_y + 55
        if is_yawning:
            # Wide open mouth oval (high MAR)
            cv2.ellipse(frame, (center_x, mouth_y), (22, 35), 0, 0, 360, (30, 30, 100), -1)
        else:
            # Closed mouth line
            cv2.ellipse(frame, (center_x, mouth_y), (22, 6), 0, 0, 180, (50, 50, 130), 3)

        # Timestamp & Phase indicator on frame
        phase_label = "NORMAL DRIVING"
        if is_eyes_closed:
            phase_label = "SIMULATED DROWSINESS (EYES CLOSED)"
        elif is_yawning:
            phase_label = "SIMULATED YAWN (MOUTH OPEN)"

        cv2.putText(frame, f"TEST CLIP | {sec:.1f}s | {phase_label}", (20, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        out.write(frame)

    out.release()
    print(f"Synthetic video generated successfully: {output_path}")
    return output_path

if __name__ == "__main__":
    create_synthetic_driver_video()
