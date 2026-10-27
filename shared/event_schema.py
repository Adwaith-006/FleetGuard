"""
Shared Event Schema.
Defines the canonical data model for driver safety events exchanged
between the Driver Monitoring Service and the Owner Management Service.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
try:
    from pydantic import BaseModel, Field
except ImportError:
    # Lightweight fallback if pydantic is not installed
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self):
            return self.__dict__
    def Field(*args, **kwargs):
        return None


class SafetyEvent(BaseModel):
    """Canonical driver safety event payload."""
    event_id: str
    event_type: str
    start_time: str
    end_time: str
    duration: float
    timestamp: Optional[str] = None
    severity: Optional[str] = "WARNING"
    status: Optional[str] = "OBSERVED"
    confidence: Optional[float] = None
    metrics: Dict[str, Any] = {}
    driver_id: Optional[str] = "DRV001"
    driver_name: Optional[str] = "Default Driver"
    vehicle_id: Optional[str] = "VEH001"
    vehicle_no: Optional[str] = "Default Vehicle"
    session_id: Optional[str] = "sess_default"


class EventStatusClassifier:
    """Classifies objective event status based on event type and duration persistence."""

    @staticmethod
    def classify_status(event_type: str, duration: float, severity: str = "WARNING") -> str:
        evt = (event_type or "").upper()

        if severity == "CRITICAL":
            return "HIGH_RISK" if ("DROWSINESS" in evt or "HEAD" in evt) else "UNSAFE"

        if "DROWSINESS" in evt:
            return "DROWSINESS_DETECTED" if duration >= 1.5 else "OBSERVED"
        elif "YAWN" in evt:
            return "ATTENTION_REQUIRED" if duration >= 2.0 else "OBSERVED"
        elif "PHONE" in evt:
            return "ATTENTION_REQUIRED" if duration >= 1.5 else "BRIEF"
        elif "HEAD" in evt or "POSTURE" in evt or "LAY" in evt:
            return "UNSAFE_POSTURE" if duration >= 1.5 else "OBSERVED"

        return "OBSERVED"
