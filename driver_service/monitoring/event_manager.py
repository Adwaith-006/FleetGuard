import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from config.settings import (
    DROWSINESS_DURATION_THRESHOLD,
    DROWSINESS_COOLDOWN,
    YAWN_MIN_DURATION,
    YAWN_COOLDOWN,
    PHONE_DURATION_THRESHOLD,
    PHONE_COOLDOWN,
    HEAD_DOWN_DURATION_THRESHOLD,
    HEAD_DOWN_COOLDOWN,
    DRIVER_ID,
    VEHICLE_ID,
    EVENTS_FILE_PATH,
    DATA_DIR
)
from models.events import DriverEvent
from monitoring.severity_manager import SeverityManager
from utils.logger import logger


class TrackedCondition:
    """Helper state holder for tracking behaviour conditions across video frames."""

    def __init__(self, duration_threshold: float, cooldown_duration: float = 0.0, drop_tolerance: float = 0.35):
        self.duration_threshold = duration_threshold
        self.cooldown_duration = cooldown_duration
        self.drop_tolerance = drop_tolerance
        self.start_time: Optional[datetime] = None
        self.last_active_time: Optional[datetime] = None
        self.last_end_time: Optional[datetime] = None
        self.is_event_active: bool = False
        self.current_event: Optional[DriverEvent] = None
        self.metrics_history: List[float] = []

    def reset(self, end_time: Optional[datetime] = None):
        if end_time is not None:
            self.last_end_time = end_time
        self.start_time = None
        self.last_active_time = None
        self.is_event_active = False
        self.current_event = None
        self.metrics_history = []


class EventManager:
    """
    Centralized Event Engine.
    Tracks raw condition persistence over time, handles state transitions,
    generates structured DriverEvent objects, prevents duplicate triggers,
    and persists completed events locally.
    """

    def __init__(
        self,
        events_file_path: str = EVENTS_FILE_PATH,
        session: Optional[Any] = None,
        driver_id: Optional[str] = None,
        vehicle_id: Optional[str] = None
    ):
        self.events_file_path = events_file_path
        self._ensure_storage_exists()
        self.session = session
        self.driver_id = driver_id or (session.driver_id if session and hasattr(session, "driver_id") else DRIVER_ID)
        self.vehicle_id = vehicle_id or (session.vehicle_id if session and hasattr(session, "vehicle_id") else VEHICLE_ID)
        self.session_id = (
            session.session_id
            if session and hasattr(session, "session_id")
            else f"sess_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        )

        self.conditions = {
            "DROWSINESS": TrackedCondition(DROWSINESS_DURATION_THRESHOLD, cooldown_duration=DROWSINESS_COOLDOWN),
            "YAWNING": TrackedCondition(YAWN_MIN_DURATION, cooldown_duration=YAWN_COOLDOWN),
            "PHONE_DETECTED": TrackedCondition(PHONE_DURATION_THRESHOLD, cooldown_duration=PHONE_COOLDOWN),
            "HEAD_DOWN": TrackedCondition(HEAD_DOWN_DURATION_THRESHOLD, cooldown_duration=HEAD_DOWN_COOLDOWN)
        }

        self.all_events: List[DriverEvent] = []

    def _ensure_storage_exists(self):
        """Creates the data directory and events.json file if they do not exist."""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not os.path.exists(self.events_file_path):
                with open(self.events_file_path, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=4)
        except Exception as e:
            logger.error(f"Error ensuring storage directory exists: {e}")

    def _save_event_to_json(self, event: DriverEvent):
        """Appends or updates an event dict in the local events.json file."""
        try:
            events_data = []
            if os.path.exists(self.events_file_path):
                with open(self.events_file_path, "r", encoding="utf-8") as f:
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

            with open(self.events_file_path, "w", encoding="utf-8") as f:
                json.dump(
                    events_data,
                    f,
                    indent=4,
                    default=lambda o: o.item() if hasattr(o, "item") else str(o)
                )

        except Exception as e:
            logger.error(f"Failed to save event to local JSON: {e}")

    def process_frame_states(
        self,
        is_eye_closed: bool,
        is_mouth_open: bool,
        is_phone_detected: bool,
        is_head_down: bool = False,
        current_ear: Optional[float] = None,
        mouth_dist: Optional[float] = None,
        phone_conf: Optional[float] = None,
        posture_metrics: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Evaluates frame-level states against persistence thresholds.
        Returns dictionary of currently active events and their severity.
        """
        now = timestamp or datetime.now(timezone.utc)

        raw_states = {
            "DROWSINESS": (is_eye_closed, current_ear),
            "YAWNING": (is_mouth_open, mouth_dist),
            "PHONE_DETECTED": (is_phone_detected, phone_conf),
            "HEAD_DOWN": (is_head_down, posture_metrics.get("roll", 0.0) if posture_metrics else None)
        }

        active_events_summary = {}

        for event_type, (is_triggered, metric_val) in raw_states.items():
            tracker = self.conditions[event_type]

            # Cooldown check
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
                tracker.last_active_time = now

                elapsed = (now - tracker.start_time).total_seconds()

                if elapsed >= tracker.duration_threshold:
                    current_severity = SeverityManager.evaluate_severity(
                        event_type, elapsed, metric_val
                    )
                    current_status = SeverityManager.classify_status(
                        event_type, elapsed, current_severity
                    )

                    if not tracker.is_event_active:
                        tracker.is_event_active = True
                        tracker.current_event = DriverEvent(
                            event_type=event_type,
                            start_time=tracker.start_time,
                            end_time=now,
                            severity=current_severity,
                            status="ACTIVE",
                            confidence=phone_conf if event_type == "PHONE_DETECTED" else None,
                            driver_id=self.driver_id,
                            vehicle_id=self.vehicle_id,
                            session_id=self.session_id
                        )
                        logger.warning(
                            f"[{event_type} STARTED] Duration: {elapsed:.1f}s | "
                            f"Severity: {current_severity} | Status: {current_status}"
                        )
                    else:
                        # Update ongoing event
                        if tracker.current_event is not None:
                            tracker.current_event.update_end(
                                end_time=now,
                                severity=current_severity,
                                status="ACTIVE"
                            )

                    active_events_summary[event_type] = {
                        "duration": round(elapsed, 1),
                        "severity": current_severity,
                        "status": current_status
                    }

            else:
                # Condition is inactive or in cooldown
                if tracker.is_event_active and tracker.start_time is not None:
                    end_time = now
                    duration = round((end_time - tracker.start_time).total_seconds(), 2)

                    # Compute aggregated metric summary
                    metrics = {}
                    if tracker.metrics_history:
                        if event_type == "DROWSINESS":
                            metrics["avg_ear"] = round(sum(tracker.metrics_history) / len(tracker.metrics_history), 3)
                            metrics["min_ear"] = round(min(tracker.metrics_history), 3)
                        elif event_type == "YAWNING":
                            metrics["max_mar"] = round(max(tracker.metrics_history), 2)
                            metrics["avg_mar"] = round(sum(tracker.metrics_history) / len(tracker.metrics_history), 2)
                        elif event_type == "PHONE_DETECTED":
                            metrics["max_confidence"] = round(max(tracker.metrics_history), 2)
                            metrics["avg_confidence"] = round(sum(tracker.metrics_history) / len(tracker.metrics_history), 2)
                        elif event_type == "HEAD_DOWN":
                            if posture_metrics:
                                metrics.update(posture_metrics)

                    final_severity = SeverityManager.evaluate_severity(event_type, duration, metric_val)
                    final_status = SeverityManager.classify_status(event_type, duration, final_severity)

                    completed_event = tracker.current_event
                    if completed_event is None:
                        completed_event = DriverEvent(
                            event_type=event_type,
                            start_time=tracker.start_time,
                            end_time=end_time,
                            severity=final_severity,
                            status=final_status,
                            confidence=phone_conf if event_type == "PHONE_DETECTED" else None,
                            metrics=metrics,
                            driver_id=self.driver_id,
                            vehicle_id=self.vehicle_id,
                            session_id=self.session_id
                        )
                    else:
                        completed_event.update_end(
                            end_time=end_time,
                            severity=final_severity,
                            status=final_status,
                            metrics=metrics
                        )

                    self.all_events.append(completed_event)
                    self._save_event_to_json(completed_event)

                    if self.session and hasattr(self.session, "record_event"):
                        self.session.record_event(event_type, final_severity)

                    # Dispatch asynchronously to FastAPI backend if configured
                    try:
                        from utils.api_client import send_event_to_backend_async
                        send_event_to_backend_async(completed_event.to_dict())
                    except Exception as err:
                        logger.debug(f"Could not dispatch event to sync client: {err}")

                    logger.info(
                        f"[{event_type} COMPLETED] Duration: {duration}s | "
                        f"Severity: {final_severity} | Status: {final_status} | ID: {completed_event.event_id}"
                    )

                    tracker.reset(end_time=end_time)
                elif tracker.start_time is not None:
                    # In pre-activation accumulation: allow brief dropout/noise tolerance
                    inactive_seconds = (now - tracker.last_active_time).total_seconds() if tracker.last_active_time else 1.0
                    if inactive_seconds >= tracker.drop_tolerance:
                        tracker.reset()
                else:
                    tracker.reset()

        return active_events_summary

    def flush_active_events(self):
        """Finalizes and persists any events that are still active when monitoring stops."""
        now = datetime.now(timezone.utc)
        for event_type, tracker in self.conditions.items():
            if tracker.is_event_active and tracker.start_time is not None:
                duration = round((now - tracker.start_time).total_seconds(), 2)
                severity = SeverityManager.evaluate_severity(event_type, duration)
                status = SeverityManager.classify_status(event_type, duration, severity)

                completed_event = tracker.current_event or DriverEvent(
                    event_type=event_type,
                    start_time=tracker.start_time,
                    end_time=now,
                    severity=severity,
                    status=status,
                    driver_id=self.driver_id,
                    vehicle_id=self.vehicle_id,
                    session_id=self.session_id
                )
                completed_event.update_end(end_time=now, severity=severity, status=status)
                self.all_events.append(completed_event)
                self._save_event_to_json(completed_event)
                logger.info(f"Flushed active event {completed_event.event_id} ({event_type}) on shutdown.")
                tracker.reset(end_time=now)

    @property
    def is_unsafe_active(self) -> bool:
        """Returns True if any unsafe event is currently active."""
        return any(cond.is_event_active for cond in self.conditions.values())

    def get_current_active_event_type(self) -> Optional[str]:
        """Returns the highest priority active event type string or None."""
        if self.conditions.get("HEAD_DOWN", None) and self.conditions["HEAD_DOWN"].is_event_active:
            return "HEAD_DOWN"
        if self.conditions["PHONE_DETECTED"].is_event_active:
            return "PHONE_DETECTED"
        if self.conditions["DROWSINESS"].is_event_active:
            return "DROWSINESS"
        if self.conditions["YAWNING"].is_event_active:
            return "YAWNING"
        return None

