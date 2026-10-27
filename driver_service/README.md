# Driver-Side Monitoring Service

A standalone, real-time edge monitoring service for commercial vehicle drivers. Captures camera frames from the laptop webcam or prerecorded video, detects drowsiness, yawning, and optional phone usage, sounds immediate local audio warnings, and records structured safety events.

## Features
- **Webcam & Prerecorded Video Support**: Run with `--source 0` for default webcam, or `--source path/to/video.mp4` for prerecorded clips.
- **MediaPipe FaceMesh**: Computes Eye Aspect Ratio (EAR) and Mouth Aspect Ratio (MAR).
- **Time-Aware Detection**: Differentiates normal blinks (<0.4s) from sustained drowsiness (>=1.5s).
- **Local Audio Alarm**: Pygame audio mixer with Windows system speaker beep fallback. Completely offline; never requires network or Gemma to alert.
- **Resilient & Optional YOLO**: Phone detection is optional; missing model weights do not block face and drowsiness detection.
- **Local Event Persistence**: Flushes completed and active events to `data/events.json`.

## Quick Start (Windows)

From repository root:

```powershell
# 1. Run with Default Laptop Webcam
python driver_service/main.py

# 2. Run with Prerecorded Video Clip
python driver_service/main.py --source data/sample_driver.mp4

# 3. Run in Headless Mode (no GUI window, logs only)
python driver_service/main.py --source data/sample_driver.mp4 --headless

# 4. Run Automated Unit Tests
pytest driver_service/tests -v
```

## Available CLI Flags

| Flag | Description | Default |
|---|---|---|
| `-s, --source` | Camera index (0, 1) or path to video file | `0` |
| `--driver-id` | Driver identifier | `DRV001` |
| `--vehicle-id` | Vehicle identifier | `VEH001` |
| `--no-alarm` | Disable local audio warning | `False` |
| `--no-phone` | Disable YOLO phone detection | `False` |
| `--headless` | Run without OpenCV display window | `False` |
