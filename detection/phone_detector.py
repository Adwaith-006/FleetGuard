import cv2
from ultralytics import YOLO
from config.settings import YOLO_MODEL_PATH, PHONE_CONFIDENCE_THRESHOLD

class PhoneDetector:
    """Wraps YOLOv8 object detection model to detect cell phone usage in frames."""

    def __init__(self, model_path=YOLO_MODEL_PATH, conf_threshold=PHONE_CONFIDENCE_THRESHOLD):
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold

    def detect(self, frame):
        """
        Runs YOLO object detection on the given frame.
        Returns:
            phone_detected (bool),
            highest_confidence (float or None),
            boxes (list of tuples [(x1, y1, x2, y2, conf)])
        """
        results = self.model(frame, verbose=False)
        phone_detected = False
        highest_conf = 0.0
        detected_boxes = []

        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = self.model.names[cls]

                if class_name == "cell phone" and conf >= self.conf_threshold:
                    phone_detected = True
                    if conf > highest_conf:
                        highest_conf = conf

                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    detected_boxes.append((x1, y1, x2, y2, conf))

        return phone_detected, (highest_conf if phone_detected else None), detected_boxes
