import os
from typing import Optional, List, Tuple, Set, Dict, Any
from config.settings import (
    YOLO_MODEL_PATH,
    PHONE_CONFIDENCE_THRESHOLD,
    PHONE_IOU_THRESHOLD,
    PHONE_DEVICE,
    ENABLE_PHONE_DETECTION,
    resolve_asset_path
)
from utils.logger import logger

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    YOLO = None
    ULTRALYTICS_AVAILABLE = False


class PhoneDetector:
    """
    Wraps YOLO object detection to identify potential mobile phone presence in camera frames.
    
    Safety & Design Notes:
    - Detecting a phone indicates object presence, not definitive proof of driver distraction.
    - Completely optional: If Ultralytics is uninstalled or weights are missing, monitoring continues
      uninterrupted for drowsiness, yawning, and face tracking.
    - Dynamically discovers cell phone classes from model metadata to support standard COCO (class 67)
      and custom fine-tuned weights without brittle hardcoding.
    """

    def __init__(
        self,
        model_path: str = YOLO_MODEL_PATH,
        conf_threshold: float = PHONE_CONFIDENCE_THRESHOLD,
        iou_threshold: float = PHONE_IOU_THRESHOLD,
        device: Optional[str] = PHONE_DEVICE,
        enabled: bool = ENABLE_PHONE_DETECTION
    ):
        self.model_path = resolve_asset_path(model_path, "yolov8n.pt")
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.device = device
        self.enabled = enabled
        self.model = None
        self.is_available = False
        self.status_reason = "OK"
        self.phone_class_ids: Set[int] = set()
        self.phone_class_names: Dict[int, str] = {}

        if not self.enabled:
            self.status_reason = "Disabled via configuration (ENABLE_PHONE_DETECTION=False)"
            logger.info("Phone detection is disabled in settings.")
            return

        if not ULTRALYTICS_AVAILABLE:
            self.status_reason = "Ultralytics package not installed"
            logger.warning(
                "Phone detection is disabled: 'ultralytics' is not installed. "
                "Webcam and drowsiness monitoring will continue normally. "
                "To enable phone detection, install it with: pip install ultralytics"
            )
            return

        if not os.path.exists(self.model_path):
            self.status_reason = f"YOLO weights not found at: {self.model_path}"
            logger.warning(
                f"Phone detection model weights missing at {self.model_path}. "
                "Phone detection disabled. Drowsiness and yawning monitoring will continue."
            )
            return

        try:
            self.model = YOLO(self.model_path)
            self._discover_phone_classes()

            if not self.phone_class_ids:
                self.is_available = False
                available_classes = list(self.model.names.values())[:10] if hasattr(self.model, "names") else []
                self.status_reason = f"No cell phone class found in model (classes: {available_classes})"
                logger.warning(
                    f"YOLO model loaded from {self.model_path}, but no phone-related class was found in its "
                    f"class list. Phone detection disabled. Sample classes: {available_classes}"
                )
                return

            self.is_available = True
            self.status_reason = "Ready"
            logger.info(
                f"Phone detection initialized with model: {self.model_path} | "
                f"Discovered phone classes: {self.phone_class_names} | "
                f"Confidence threshold: {self.conf_threshold:.2f} | IoU: {self.iou_threshold:.2f}"
            )
        except Exception as e:
            self.is_available = False
            self.status_reason = f"Model loading error: {e}"
            logger.error(f"Failed to load YOLO model from {self.model_path}: {e}. Phone detection disabled.")

    def _discover_phone_classes(self):
        """Inspects model class names dynamically to identify phone classes."""
        self.phone_class_ids.clear()
        self.phone_class_names.clear()

        if self.model is None or not hasattr(self.model, "names"):
            return

        raw_names = self.model.names
        items = raw_names.items() if isinstance(raw_names, dict) else enumerate(raw_names)

        target_tokens = ("cell phone", "phone", "mobile phone", "telephone", "cellphone")

        for cls_id, raw_name in items:
            name_str = str(raw_name).lower().strip()
            # Match exact target token or ensure 'phone' is a distinct word
            if any(tok in name_str for tok in target_tokens):
                cls_int = int(cls_id)
                self.phone_class_ids.add(cls_int)
                self.phone_class_names[cls_int] = str(raw_name)

    def detect(self, frame) -> Tuple[bool, Optional[float], List[Tuple[int, int, int, int, float]]]:
        """
        Runs YOLO object detection on the given frame to identify cell phones.
        
        Args:
            frame: OpenCV image array (BGR), or None.
            
        Returns:
            Tuple of:
                - phone_detected: bool
                - highest_confidence: float or None
                - detected_boxes: list of (x1, y1, x2, y2, conf)
        """
        if not self.enabled or not self.is_available or self.model is None or frame is None:
            return False, None, []

        try:
            kwargs: Dict[str, Any] = {
                "conf": self.conf_threshold,
                "iou": self.iou_threshold,
                "verbose": False
            }
            if self.device:
                kwargs["device"] = self.device

            results = self.model(frame, **kwargs)
            phone_detected = False
            highest_conf = 0.0
            detected_boxes: List[Tuple[int, int, int, int, float]] = []

            for r in results:
                if not hasattr(r, "boxes") or r.boxes is None:
                    continue

                for box in r.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])

                    if cls in self.phone_class_ids and conf >= self.conf_threshold:
                        phone_detected = True
                        if conf > highest_conf:
                            highest_conf = conf

                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        detected_boxes.append((x1, y1, x2, y2, conf))

                        logger.debug(
                            f"[PHONE INFERENCE] Detected class '{self.phone_class_names.get(cls, cls)}' "
                            f"(ID: {cls}) with confidence {conf:.2f} at box [{x1}, {y1}, {x2}, {y2}]"
                        )

            return phone_detected, (highest_conf if phone_detected else None), detected_boxes

        except Exception as e:
            logger.debug(f"Error during phone detection inference: {e}")
            return False, None, []

