# Configuration settings for AI Driver Behaviour and Safety Monitoring System

import os

# Try loading .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# CAMERA / VIDEO INPUT SETTINGS
# VIDEO_SOURCE can be an integer string ('0') for webcam or a path to a video file ('test.mp4')
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "0")
try:
    CAMERA_INDEX = int(VIDEO_SOURCE)
except ValueError:
    CAMERA_INDEX = VIDEO_SOURCE

FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "640"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "480"))

# DRIVER & VEHICLE IDENTIFIERS
DRIVER_ID = os.getenv("DRIVER_ID", "DRV001")
VEHICLE_ID = os.getenv("VEHICLE_ID", "VEH001")
TIMEZONE = os.getenv("TIMEZONE", "UTC")

# DROWSINESS DETECTION THRESHOLDS
# Standard 6-point MediaPipe FaceMesh EAR: Open ~0.24-0.32, Closed ~0.04-0.10. Calibrated threshold: 0.21
EAR_THRESHOLD = float(os.getenv("EAR_THRESHOLD", "0.21"))
DROWSINESS_DURATION_THRESHOLD = float(os.getenv("DROWSINESS_DURATION_THRESHOLD", "1.5"))
BLINK_MAX_DURATION = float(os.getenv("BLINK_MAX_DURATION", "0.4"))
DROWSINESS_COOLDOWN = float(os.getenv("DROWSINESS_COOLDOWN", "2.0"))

# YAWNING DETECTION THRESHOLDS (Normalized Mouth Aspect Ratio - MAR)
# Normal talking / smiling: MAR ~0.15-0.35. Yawning: MAR ~0.50-0.75.
# Calibrated default: 0.50 (distinguishes wide yawn from speech while remaining reachable).
YAWN_MAR_THRESHOLD = float(os.getenv("YAWN_MAR_THRESHOLD", "0.50"))
YAWN_MIN_DURATION = float(os.getenv("YAWN_MIN_DURATION", "2.0"))
YAWN_COOLDOWN = float(os.getenv("YAWN_COOLDOWN", "3.0"))
MOUTH_OPEN_THRESHOLD = YAWN_MAR_THRESHOLD  # Alias for backward compatibility
YAWN_DURATION_THRESHOLD = YAWN_MIN_DURATION  # Alias for backward compatibility

# DIRECTORY & ASSET PATHS
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_DIR = os.path.dirname(CONFIG_DIR)
ROOT_DIR = os.path.dirname(SERVICE_DIR)
ASSETS_DIR = os.path.join(SERVICE_DIR, "assets")


def resolve_asset_path(filename_or_path: str, default_name: str) -> str:
    """
    Robustly resolves asset paths across different working directories and relative configs.
    Checks exact path, assets dir, service dir, and repo root.
    """
    raw = filename_or_path if filename_or_path else default_name
    candidates = [
        raw,
        os.path.join(ASSETS_DIR, raw),
        os.path.join(SERVICE_DIR, raw),
        os.path.join(ROOT_DIR, raw),
        os.path.join(ASSETS_DIR, os.path.basename(raw)),
        os.path.join(ROOT_DIR, "driver_service", "assets", os.path.basename(raw)),
        os.path.join(ROOT_DIR, os.path.basename(raw)),
    ]
    if not filename_or_path or filename_or_path == default_name:
        candidates.append(os.path.join(SERVICE_DIR, "assets", default_name))
        candidates.append(os.path.join(ASSETS_DIR, default_name))

    for c in candidates:
        if c and os.path.exists(c):
            return os.path.abspath(c)
    # If not found yet, return absolute path in ASSETS_DIR as fallback target
    return os.path.abspath(os.path.join(ASSETS_DIR, os.path.basename(raw)))


# PHONE DETECTION SETTINGS
ENABLE_PHONE_DETECTION = os.getenv("ENABLE_PHONE_DETECTION", "True").lower() in ("true", "1", "yes")
PHONE_CONFIDENCE_THRESHOLD = float(os.getenv("PHONE_CONFIDENCE_THRESHOLD", "0.45"))
PHONE_IOU_THRESHOLD = float(os.getenv("PHONE_IOU_THRESHOLD", "0.45"))
PHONE_DURATION_THRESHOLD = float(os.getenv("PHONE_DURATION_THRESHOLD", "1.5"))
PHONE_COOLDOWN = float(os.getenv("PHONE_COOLDOWN", "3.0"))
PHONE_DEVICE = os.getenv("PHONE_DEVICE", None)

_raw_yolo = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")
YOLO_MODEL_PATH = resolve_asset_path(_raw_yolo, "yolov8n.pt")

# ALARM SETTINGS
ALARM_ENABLED = os.getenv("ALARM_ENABLED", "True").lower() in ("true", "1", "yes")
_raw_alarm = os.getenv("ALARM_SOUND_PATH", "alarm.mp3")
ALARM_SOUND_PATH = resolve_asset_path(_raw_alarm, "alarm.mp3")
ALARM_VOLUME = float(os.getenv("ALARM_VOLUME", "1.0"))

# LOCAL EVENT PERSISTENCE
DATA_DIR = os.path.abspath(os.getenv("DATA_DIR", os.path.join(SERVICE_DIR, "data")))
EVENTS_FILE_PATH = os.path.abspath(os.getenv("EVENTS_FILE_PATH", os.path.join(DATA_DIR, "events.json")))

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000/api/events")
BACKEND_STATUS_URL = os.getenv("BACKEND_STATUS_URL", "http://127.0.0.1:8000/api/drivers/status")

# POSTURE / HEAD DOWN / LAY DOWN DETECTION SETTINGS
ENABLE_POSTURE_DETECTION = os.getenv("ENABLE_POSTURE_DETECTION", "True").lower() in ("true", "1", "yes")
HEAD_DOWN_DURATION_THRESHOLD = float(os.getenv("HEAD_DOWN_DURATION_THRESHOLD", "1.5"))
HEAD_DOWN_COOLDOWN = float(os.getenv("HEAD_DOWN_COOLDOWN", "3.0"))
HEAD_PITCH_DOWN_THRESHOLD = float(os.getenv("HEAD_PITCH_DOWN_THRESHOLD", "-20.0"))
HEAD_ROLL_THRESHOLD = float(os.getenv("HEAD_ROLL_THRESHOLD", "28.0"))
HEAD_SLUMP_Y_THRESHOLD = float(os.getenv("HEAD_SLUMP_Y_THRESHOLD", "0.68"))

# FACIAL LANDMARKS (MediaPipe 468 landmarks mesh)
LEFT_EYE_LANDMARKS = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_LANDMARKS = [362, 385, 387, 263, 373, 380]
UPPER_LIP_LANDMARK = 13
LOWER_LIP_LANDMARK = 14
MOUTH_LEFT_CORNER = 61
MOUTH_RIGHT_CORNER = 291
FOREHEAD_LANDMARK = 10
NOSE_TIP_LANDMARK = 1
CHIN_LANDMARK = 152


