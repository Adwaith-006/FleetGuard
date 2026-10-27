import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from config.settings import DRIVER_ID, VEHICLE_ID


class DrivingSession:
    """Manages driving session metadata, duration, and event counts for the vehicle system."""

    def __init__(self, driver_id: Optional[str] = None, vehicle_id: Optional[str] = None):
        self.session_id = f"sess_{uuid.uuid4().hex[:8]}"
        self.driver_id = driver_id or DRIVER_ID
        self.vehicle_id = vehicle_id or VEHICLE_ID
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        
        self.drowsiness_count = 0
        self.yawning_count = 0
        self.phone_count = 0
        self.head_down_count = 0
        self.critical_count = 0
        self.warning_count = 0

    def record_event(self, event_type: str, severity: str):
        """Increments session counters based on completed event details."""
        evt = (event_type or "").upper()
        if "DROWSINESS" in evt:
            self.drowsiness_count += 1
        elif "YAWN" in evt:
            self.yawning_count += 1
        elif "PHONE" in evt:
            self.phone_count += 1
        elif "HEAD" in evt or "LAY" in evt or "POSTURE" in evt:
            self.head_down_count += 1

        if severity == "CRITICAL":
            self.critical_count += 1
        elif severity == "WARNING":
            self.warning_count += 1

    def close(self):
        """Finalizes the driving session."""
        if self.end_time is None:
            self.end_time = datetime.now(timezone.utc)

    def get_summary(self) -> Dict[str, Any]:
        """Returns session summary metrics."""
        end = self.end_time or datetime.now(timezone.utc)
        duration = round((end - self.start_time).total_seconds(), 1)
        return {
            "session_id": self.session_id,
            "driver_id": self.driver_id,
            "vehicle_id": self.vehicle_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end.isoformat(),
            "duration_seconds": duration,
            "drowsiness_count": self.drowsiness_count,
            "yawning_count": self.yawning_count,
            "phone_count": self.phone_count,
            "head_down_count": self.head_down_count,
            "warning_count": self.warning_count,
            "critical_count": self.critical_count
        }

