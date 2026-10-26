import uuid
from datetime import datetime
from typing import Dict, Any, Optional

class DrivingSession:
    """Manages driving session metadata, duration, and event counts for the vehicle system."""

    def __init__(self, driver_id: Optional[str] = None, vehicle_id: Optional[str] = None):
        self.session_id = f"sess_{uuid.uuid4().hex[:8]}"
        self.driver_id = driver_id
        self.vehicle_id = vehicle_id
        self.start_time = datetime.now()
        
        self.drowsiness_count = 0
        self.yawning_count = 0
        self.phone_count = 0
        self.critical_count = 0

    def record_event(self, event_type: str, severity: str):
        """Increments session counters based on completed event details."""
        if event_type == "DROWSINESS":
            self.drowsiness_count += 1
        elif event_type == "YAWNING":
            self.yawning_count += 1
        elif event_type == "PHONE_DETECTED":
            self.phone_count += 1

        if severity == "CRITICAL":
            self.critical_count += 1

    def get_summary(self) -> Dict[str, Any]:
        """Returns session summary metrics."""
        duration = round((datetime.now() - self.start_time).total_seconds(), 1)
        return {
            "session_id": self.session_id,
            "driver_id": self.driver_id,
            "vehicle_id": self.vehicle_id,
            "start_time": self.start_time.isoformat(),
            "duration_seconds": duration,
            "drowsiness_count": self.drowsiness_count,
            "yawning_count": self.yawning_count,
            "phone_count": self.phone_count,
            "critical_count": self.critical_count
        }
