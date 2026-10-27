import cv2
import os
import time
from typing import Optional, Tuple, Union
from config.settings import CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT
from utils.logger import logger


class CameraManager:
    """
    Manages video frame capture for webcams and prerecorded video files.
    
    Features:
    - Automatic webcam / file source detection
    - Graceful handling of missing hardware, stream disconnects, and EOF
    - Optional video looping for prerecorded test videos
    - Mirroring for intuitive webcam display (disabled for video files)
    - Resource cleanup on shutdown
    """

    def __init__(
        self,
        source: Union[int, str] = CAMERA_INDEX,
        width: int = FRAME_WIDTH,
        height: int = FRAME_HEIGHT,
        loop_video: bool = True,
        mirror: Optional[bool] = None
    ):
        self.raw_source = source
        self.width = width
        self.height = height
        self.loop_video = loop_video

        # Determine source type
        self.is_video_file = isinstance(source, str) and not source.isdigit()
        if self.is_video_file:
            self.source = os.path.abspath(source) if not os.path.isabs(source) else source
            # For prerecorded files, default to no mirror flip unless explicitly requested
            self.mirror = mirror if mirror is not None else False
        else:
            self.source = int(source)
            # For webcam, default to mirror view (selfie mode)
            self.mirror = mirror if mirror is not None else True

        self.cap: Optional[cv2.VideoCapture] = None
        self.is_opened = False
        self.fps: float = 30.0
        self.frame_count: int = 0
        self.consecutive_failures: int = 0
        self.max_consecutive_failures: int = 10

    def start(self) -> Tuple[bool, str]:
        """
        Initializes and opens the video capture device or file.
        Returns:
            Tuple of (success: bool, message: str)
        """
        if self.is_opened and self.cap is not None:
            return True, "Camera is already running."

        if self.is_video_file:
            if not os.path.exists(self.source):
                err_msg = f"Prerecorded video file not found: {self.source}"
                logger.error(err_msg)
                return False, err_msg
            logger.info(f"Opening video file source: {self.source}")
            self.cap = cv2.VideoCapture(self.source)
        else:
            logger.info(f"Opening webcam index: {self.source} (DSHOW backend preferred)")
            # On Windows, cv2.CAP_DSHOW initializes faster and prevents backend hangs
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                # Fallback to default backend
                logger.warning(f"DSHOW backend failed for index {self.source}. Trying default backend...")
                self.cap = cv2.VideoCapture(self.source)

        if not self.cap or not self.cap.isOpened():
            err_msg = (
                f"Failed to open video source: '{self.raw_source}'. "
                "Ensure webcam is connected and not in use by another application."
            )
            logger.error(err_msg)
            self.is_opened = False
            return False, err_msg

        # Configure resolution
        if not self.is_video_file:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        cap_fps = self.cap.get(cv2.CAP_PROP_FPS)
        if cap_fps and cap_fps > 0:
            self.fps = cap_fps

        self.is_opened = True
        logger.info(
            f"Camera initialized successfully. Source: {self.source} | "
            f"Type: {'File' if self.is_video_file else 'Webcam'} | FPS: {self.fps:.1f}"
        )
        return True, "Camera opened successfully."

    def read(self) -> Tuple[bool, Optional[any]]:
        """
        Reads a frame from the capture source.
        Returns:
            Tuple of (success: bool, frame: np.ndarray or None)
        """
        if not self.is_opened or self.cap is None:
            return False, None

        success, frame = self.cap.read()

        if not success or frame is None:
            self.consecutive_failures += 1

            # Handle end-of-file for prerecorded video
            if self.is_video_file and self.loop_video:
                # Rewind video to beginning
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = self.cap.read()
                if success and frame is not None:
                    self.consecutive_failures = 0
                    if self.mirror:
                        frame = cv2.flip(frame, 1)
                    return True, frame

            if self.consecutive_failures >= self.max_consecutive_failures:
                logger.error(
                    f"Exceeded max consecutive frame read failures ({self.max_consecutive_failures}). "
                    "Camera may have been disconnected."
                )
                return False, None

            # Small yield to prevent CPU spin during transient glitches
            time.sleep(0.01)
            return False, None

        self.consecutive_failures = 0
        self.frame_count += 1

        if self.mirror:
            frame = cv2.flip(frame, 1)

        return True, frame

    def release(self):
        """Releases the camera and resets state cleanly."""
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception as e:
                logger.warning(f"Error releasing video capture: {e}")
            self.cap = None

        self.is_opened = False
        logger.info("Camera resources released successfully.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
