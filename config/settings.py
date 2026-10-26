# Configuration settings for AI Driver Behaviour and Safety Monitoring System

import os

# CAMERA SETTINGS
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# DETECTION THRESHOLDS
EAR_THRESHOLD = 0.41               # Eye Aspect Ratio threshold for drowsiness
DROWSINESS_DURATION_THRESHOLD = 1.0 # Seconds eyes must remain closed before event starts

# YAWNING DETECTION THRESHOLDS (Normalized Mouth Aspect Ratio - MAR)
YAWN_MAR_THRESHOLD = 0.60          # Mouth Aspect Ratio (height / width) threshold
YAWN_MIN_DURATION = 2.0            # Seconds mouth must remain wide open for a valid yawn
YAWN_COOLDOWN = 3.0                # Cooldown period (seconds) after a yawn before a new event can start
MOUTH_OPEN_THRESHOLD = YAWN_MAR_THRESHOLD # Alias for backward compatibility
YAWN_DURATION_THRESHOLD = YAWN_MIN_DURATION # Alias for backward compatibility

PHONE_CONFIDENCE_THRESHOLD = 0.50  # YOLO confidence threshold for phone detection
PHONE_DURATION_THRESHOLD = 1.0     # Seconds phone must be detected before event starts

# ALARM SETTINGS
ALARM_ENABLED = True
ALARM_SOUND_PATH = os.path.abspath("alarm.mp3")

# YOLO MODEL SETTINGS
YOLO_MODEL_PATH = os.path.abspath("yolov8n.pt")

# LOCAL EVENT PERSISTENCE
DATA_DIR = os.path.abspath("data")
EVENTS_FILE_PATH = os.path.join(DATA_DIR, "events.json")

# FACIAL LANDMARKS (MediaPipe 468 landmarks mesh)
LEFT_EYE_LANDMARKS = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_LANDMARKS = [362, 385, 387, 263, 373, 380]
UPPER_LIP_LANDMARK = 13
LOWER_LIP_LANDMARK = 14
MOUTH_LEFT_CORNER = 61
MOUTH_RIGHT_CORNER = 291
