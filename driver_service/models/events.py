import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from config.settings import DRIVER_ID, VEHICLE_ID, TIMEZONE


def get_current_iso_timestamp() -> str:
    """Returns current ISO 8601 timestamp with UTC timezone indication."""
    return datetime.now(timezone.utc).isoformat()


class DriverEvent:
    """
    Represents a structured driver behaviour safety event.
    
    Compatible with the FastAPI backend SafetyEventPayload schema.
    Timestamps follow ISO-8601 UTC standard.
    """

    def __init__(
        self,
        event_type: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity: str = "WARNING",
        status: str = "COMPLETED",
        confidence: Optional[float] = None,
        metrics: Optional[Dict[str, Any]] = None,
        driver_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        session_id: Optional[str] = None,
        event_id: Optional[str] = None
    ):
        self.event_id = event_id or f"evt_{uuid.uuid4().hex[:8]}"
        self.event_type = event_type
        self.start_time = start_time or datetime.now(timezone.utc)
        self.end_time = end_time or datetime.now(timezone.utc)
        
        # Calculate duration in seconds
        delta = (self.end_time - self.start_time).total_seconds()
        self.duration = max(0.0, round(delta, 2))
        
        self.severity = severity
        self.status = status
        self.confidence = confidence
        self.metrics = metrics or {}
        
        self.driver_id = driver_id or DRIVER_ID
        self.vehicle_id = vehicle_id or VEHICLE_ID
        self.session_id = session_id

    def update_end(
        self,
        end_time: datetime,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None
    ):
        """Updates the end timestamp, duration, and optional metrics for an active event."""
        self.end_time = end_time
        delta = (self.end_time - self.start_time).total_seconds()
        self.duration = max(0.0, round(delta, 2))
        if severity:
            self.severity = severity
        if status:
            self.status = status
        if metrics:
            self.metrics.update(metrics)

    def to_dict(self) -> Dict[str, Any]:
        """Converts event to dictionary format for JSON storage and FastAPI payload."""
        start_iso = self.start_time.isoformat() if isinstance(self.start_time, datetime) else str(self.start_time)
        end_iso = self.end_time.isoformat() if isinstance(self.end_time, datetime) else str(self.end_time)

        clean_metrics = {}
        for k, v in (self.metrics or {}).items():
            if hasattr(v, "item"):
                clean_metrics[k] = v.item()
            elif isinstance(v, (int, float, str, bool)) or v is None:
                clean_metrics[k] = v
            else:
                clean_metrics[k] = str(v)

        return {
            "event_id": self.event_id,
            "driver_id": self.driver_id,
            "vehicle_id": self.vehicle_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "start_time": start_iso,
            "end_time": end_iso,
            "duration": self.duration,
            "severity": self.severity,
            "status": self.status,
            "confidence": round(float(self.confidence), 2) if self.confidence is not None else None,
            "metrics": clean_metrics,
            "timestamp": end_iso
        }

