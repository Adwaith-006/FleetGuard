import uuid
from datetime import datetime
from typing import Dict, Any, Optional

class DriverEvent:
    """Represents a structured driver behaviour safety event."""
    
    def __init__(
        self,
        event_type: str,
        start_time: datetime,
        end_time: datetime,
        severity: str,
        confidence: Optional[float] = None,
        metrics: Optional[Dict[str, Any]] = None,
        driver_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        self.event_id = f"evt_{uuid.uuid4().hex[:8]}"
        self.event_type = event_type
        self.start_time = start_time
        self.end_time = end_time
        self.duration = round((end_time - start_time).total_seconds(), 2)
        self.severity = severity
        self.confidence = confidence
        self.metrics = metrics or {}
        
        # Placeholders for future backend/session integration
        self.driver_id = driver_id
        self.vehicle_id = vehicle_id
        self.session_id = session_id

    def to_dict(self) -> Dict[str, Any]:
        """Converts event to dictionary format for JSON storage and API payload."""
        return {
            "event_id": self.event_id,
            "driver_id": self.driver_id,
            "vehicle_id": self.vehicle_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration": self.duration,
            "severity": self.severity,
            "confidence": round(self.confidence, 2) if self.confidence is not None else None,
            "metrics": self.metrics,
            "timestamp": self.end_time.isoformat()
        }
