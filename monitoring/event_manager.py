import os
import json
from datetime import datetime
from typing import Dict,Any,List,Optional

from config.settings import (
    DROWSINESS_DURATION_THRESHOLD,
    YAWN_MIN_DURATION,
    YAWN_COOLDOWN,
    PHONE_DURATION_THRESHOLD,
    EVENTS_FILE_PATH,
    DATA_DIR
)
from models.events import DriverEvent
from monitoring.severity_manager import SeverityManager
from utils.logger import logger

class TrackedCondition:
    """Helper state holder for a single behaviour condition."""
    def __init__(self, duration_threshold: float, cooldown_duration: float = 0.0):
        self.duration_threshold = duration_threshold
        self.cooldown_duration = cooldown_duration
        self.start_time: Optional[datetime] = None
        self.last_end_time: Optional[datetime] = None
        self.is_event_active: bool = False
        self.peak_metric: float = 0.0
        self.metrics_history: List[float] = []

    def reset(self, end_time: Optional[datetime] = None):
        if end_time is not None:
            self.last_end_time = end_time
        self.start_time = None
        self.is_event_active = False
        self.peak_metric = 0.0
        self.metrics_history = []


class EventManager:
    """
    Centralized Event Engine.
    Tracks raw condition persistence over time, handles state transitions,
    generates structured DriverEvent objects, and persists them locally.
    """

    def __init__(self, events_file_path: str = EVENTS_FILE_PATH, session: Optional[Any] = None):
        self.events_file_path = events_file_path
        self._ensure_storage_exists()
        self.session = session
        self.session_id = session.session_id if session and hasattr(session, "session_id") else f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.conditions = {
            "DROWSINESS": TrackedCondition(DROWSINESS_DURATION_THRESHOLD),
            "YAWNING": TrackedCondition(YAWN_MIN_DURATION, cooldown_duration=YAWN_COOLDOWN),
            "PHONE_DETECTED": TrackedCondition(PHONE_DURATION_THRESHOLD)
        }

        self.all_events: List[DriverEvent] = []

    def _ensure_storage_exists(self):
        """Creates the data directory and events.json file if they do not exist."""
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(self.events_file_path):
            with open(self.events_file_path, "w") as f:
                json.dump([], f, indent=4)

    def _save_event_to_json(self, event: DriverEvent):
        """Appends or updates an event dict in the local data/events.json file."""
        try:
            events_data = []
            if os.path.exists(self.events_file_path):
                with open(self.events_file_path, "r") as f:
                    try:
                        events_data = json.load(f)
                    except json.JSONDecodeError:
                        events_data = []

            # Check if event already exists
            existing_idx = None
            for idx, e in enumerate(events_data):
                if e.get("event_id") == event.event_id:
                    existing_idx = idx
                    break

            if existing_idx is not None:
                events_data[existing_idx].update(event.to_dict())
            else:
                events_data.append(event.to_dict())

            with open(self.events_file_path, "w") as f:
                json.dump(events_data, f, indent=4)

        except Exception as e:
            logger.error(f"Failed to save event to local JSON: {e}")

    def process_frame_states(
        self,
        is_eye_closed: bool,
        is_mouth_open: bool,
        is_phone_detected: bool,
        current_ear: Optional[float] = None,
        mouth_dist: Optional[float] = None,
        phone_conf: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluates frame-level states against persistence thresholds.
        Returns dictionary of currently active events and overall status.
        """
        now = datetime.now()

        # Update raw states map
        raw_states = {
            "DROWSINESS": (is_eye_closed, current_ear),
            "YAWNING": (is_mouth_open, mouth_dist),
            "PHONE_DETECTED": (is_phone_detected, phone_conf)
        }

        active_events_summary = {}

        for event_type, (is_triggered, metric_val) in raw_states.items():
            tracker = self.conditions[event_type]

            # Cooldown enforcement
            in_cooldown = False
            if tracker.last_end_time is not None and tracker.cooldown_duration > 0:
                time_since_last = (now - tracker.last_end_time).total_seconds()
                if time_since_last < tracker.cooldown_duration:
                    in_cooldown = True

            if is_triggered and not in_cooldown:
                if metric_val is not None:
                    tracker.metrics_history.append(metric_val)

                if tracker.start_time is None:
                    tracker.start_time = now

                elapsed = (now - tracker.start_time).total_seconds()

                if elapsed >= tracker.duration_threshold:
                    if not tracker.is_event_active:
                        tracker.is_event_active = True
                        logger.warning(
                            f"[{event_type}] Persistence threshold ({tracker.duration_threshold}s) exceeded! Event ACTIVE."
                        )

                    current_severity = SeverityManager.evaluate_severity(
                        event_type, elapsed, metric_val
                    )
                    active_events_summary[event_type] = {
                        "duration": round(elapsed, 1),
                        "severity": current_severity
                    }

            else:
                # Raw condition cleared or in cooldown
                if tracker.is_event_active and tracker.start_time is not None:
                    end_time = now
                    duration = round((end_time - tracker.start_time).total_seconds(), 2)

                    # Compute aggregated metric summary
                    metrics = {}
                    if tracker.metrics_history:
                        if event_type == "DROWSINESS":
                            metrics["avg_ear"] = round(sum(tracker.metrics_history) / len(tracker.metrics_history), 3)
                        elif event_type == "YAWNING":
                            metrics["max_mar"] = round(max(tracker.metrics_history), 2)
                        elif event_type == "PHONE_DETECTED":
                            metrics["max_confidence"] = round(max(tracker.metrics_history), 2)

                    severity = SeverityManager.evaluate_severity(
                        event_type, duration, metric_val
                    )

                    new_event = DriverEvent(
                        event_type=event_type,
                        start_time=tracker.start_time,
                        end_time=end_time,
                        severity=severity,
                        confidence=phone_conf if event_type == "PHONE_DETECTED" else None,
                        metrics=metrics,
                        driver_id="DRV001",
                        vehicle_id="VEH001",
                        session_id=self.session_id
                    )

                    self.all_events.append(new_event)
                    self._save_event_to_json(new_event)

                    if self.session and hasattr(self.session, "record_event"):
                        self.session.record_event(event_type, severity)

                    # Transmit event payload asynchronously to FastAPI backend & WebSocket
                    try:
                        from sync.api_client import send_event_to_backend_async
                        send_event_to_backend_async(new_event.to_dict())
                    except Exception as err:
                        logger.warning(f"Could not dispatch event to sync client: {err}")

                    logger.info(
                        f"[{event_type} ENDED] Duration: {duration}s | Severity: {severity} | Event ID: {new_event.event_id}"
                    )

                    tracker.reset(end_time=end_time)
                else:
                    tracker.reset()

        return active_events_summary

        return active_events_summary

    @property
    def is_unsafe_active(self) -> bool:
        """Returns True if any unsafe event is currently active."""
        return any(cond.is_event_active for cond in self.conditions.values())

    def get_current_active_event_type(self) -> Optional[str]:
        """Returns the highest priority active event type string or None."""
        if self.conditions["PHONE_DETECTED"].is_event_active:
            return "PHONE_DETECTED"
        if self.conditions["DROWSINESS"].is_event_active:
            return "DROWSINESS"
        if self.conditions["YAWNING"].is_event_active:
            return "YAWNING"
        return None
