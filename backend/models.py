from pydantic import BaseModel
from typing import Dict, Any, Optional

class EventStatusClassifier:
    """Classifies objective event status based on event type and duration persistence."""

    @staticmethod
    def classify_status(event_type: str, duration: float) -> str:
        evt_type = (event_type or "").upper()

        if "PHONE" in evt_type:
            if duration < 3.0:
                return "BRIEF"
            elif duration <= 5.0:
                return "ATTENTION_REQUIRED"
            else:
                return "UNSAFE"

        elif evt_type == "YAWNING":
            if duration < 3.5:
                return "OBSERVED"
            else:
                return "ATTENTION_REQUIRED"

        elif evt_type == "DROWSINESS":
            if duration < 2.5:
                return "DROWSINESS_DETECTED"
            else:
                return "HIGH_RISK"

        return "OBSERVED"


class SafetyEventPayload(BaseModel):
    event_id: str
    event_type: str
    start_time: str
    end_time: str
    duration: float
    timestamp: Optional[str] = None
    confidence: Optional[float] = None
    metrics: Dict[str, Any] = {}
    status: Optional[str] = None
    severity: Optional[str] = None
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None
    vehicle_id: Optional[str] = None
    vehicle_no: Optional[str] = None
    session_id: Optional[str] = None
