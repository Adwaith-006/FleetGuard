"""
Dedicated Risk Evaluation Layer for Driver Safety & Fleet Monitoring.
Evaluates camera-derived temporal evidence and MongoDB historical telemetry
against deterministic risk rules.
Handles incident-level deduplication, escalation, recovery, and optional Gemma enrichment.
"""

import uuid
import threading
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

from owner_service.backend.config.risk_settings import (
    ROLLING_WINDOW_SECONDS,
    MIN_VALID_OBSERVATIONS,
    HIGH_RISK_DROWSINESS_RATIO,
    HIGH_RISK_CONSECUTIVE_CLOSURE_SEC,
    HIGH_RISK_MIN_DROWSINESS_EVENTS,
    CRITICAL_RISK_CONTINUOUS_CLOSURE_SEC,
    CRITICAL_RISK_HEAD_DOWN_SEC,
    RECOVERY_STREAK_SECONDS,
    ESCALATION_ENABLED
)
from owner_service.backend.database import (
    get_all_events,
    save_urgent_alert,
    get_active_alert,
    resolve_urgent_alert,
    update_alert_explanation
)
from owner_service.backend.websocket import manager
from owner_service.ai.gemma_service import GemmaService

logger = logging.getLogger("RiskEvaluator")
_gemma = GemmaService()


class DriverRiskState:
    """Tracks continuous incident lifecycle and deduplication state per driver."""

    def __init__(self, driver_id: str):
        self.driver_id = driver_id
        self.active_alert_id: Optional[str] = None
        self.active_risk_level: Optional[str] = None
        self.incident_start_time: Optional[datetime] = None
        self.last_alert_time: Optional[datetime] = None
        self.normal_streak_seconds: float = 0.0
        self.last_update_time: Optional[datetime] = None


class RiskEvaluator:
    """
    Central Risk Evaluator.
    Evaluates temporal telemetry & MongoDB events to detect sustained HIGH and CRITICAL risk states.
    Prevents duplicate alerts for the same continuous incident.
    """

    _states: Dict[str, DriverRiskState] = {}
    _lock = threading.Lock()

    @classmethod
    def get_driver_state(cls, driver_id: str) -> DriverRiskState:
        with cls._lock:
            if driver_id not in cls._states:
                state = DriverRiskState(driver_id)
                # Check if there is an existing ACTIVE alert in MongoDB (e.g. across restart)
                try:
                    existing = get_active_alert(driver_id)
                    if existing:
                        state.active_alert_id = existing.get("alert_id")
                        state.active_risk_level = existing.get("risk_level")
                        state.incident_start_time = datetime.now(timezone.utc)
                except Exception as e:
                    logger.debug(f"State recovery notice: {e}")
                cls._states[driver_id] = state
            return cls._states[driver_id]

    @classmethod
    def evaluate_telemetry(cls, telemetry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluates real-time driver telemetry (from /api/drivers/status).
        Returns newly generated urgent alert dict if a new HIGH/CRITICAL incident or escalation occurred,
        otherwise None.
        """
        driver_id = telemetry.get("driver_id", "DRV001")
        vehicle_id = telemetry.get("vehicle_id", "VEH001")
        status_label = telemetry.get("status", "Attentive")
        metrics = telemetry.get("metrics", {})
        temporal = metrics.get("temporal", {})

        now = datetime.now(timezone.utc)
        state = cls.get_driver_state(driver_id)

        # 1. Extract Temporal Evidence
        data_quality_ok = temporal.get("data_quality_ok", True)
        valid_frames = temporal.get("valid_face_frames", 30)
        drowsiness_ratio = float(temporal.get("drowsiness_ratio") or 0.0)
        consecutive_closed_sec = float(temporal.get("consecutive_closed_sec") or 0.0)
        posture = metrics.get("posture", "UPRIGHT")
        ear = metrics.get("ear")

        # Track elapsed time since last update for recovery streak
        elapsed_since_last = 1.0
        if state.last_update_time:
            elapsed_since_last = max(0.1, min(5.0, (now - state.last_update_time).total_seconds()))
        state.last_update_time = now

        # 2. Check Recent Events from MongoDB within the rolling window
        recent_drowsiness_count = 0
        try:
            cutoff = now - timedelta(seconds=ROLLING_WINDOW_SECONDS)
            recent_events = get_all_events(
                limit=15,
                driver_id=driver_id,
                start_time=cutoff
            )
            recent_drowsiness_count = sum(
                1 for e in recent_events if "DROWSINESS" in (e.get("event_type") or "")
            )
        except Exception as e:
            logger.debug(f"Recent events fetch notice: {e}")

        # 3. Deterministic Risk Evaluation Rules
        detected_risk: str = "LOW"
        trigger_reason: str = ""
        evidence_dict: Dict[str, Any] = {
            "drowsiness_ratio": drowsiness_ratio,
            "consecutive_closed_sec": consecutive_closed_sec,
            "recent_drowsiness_count": recent_drowsiness_count,
            "head_pose": posture,
            "ear": ear,
            "valid_face_frames": valid_frames,
            "window_seconds": ROLLING_WINDOW_SECONDS
        }

        # Rule CRITICAL-1: Extreme uninterrupted eye closure
        if consecutive_closed_sec >= CRITICAL_RISK_CONTINUOUS_CLOSURE_SEC:
            detected_risk = "CRITICAL"
            trigger_reason = f"Extreme continuous eye closure of {consecutive_closed_sec:.1f}s"
        # Rule CRITICAL-2: Prolonged slumped/unconscious head posture
        elif posture in ("HEAD_DOWN", "LAYING_SIDEWAYS") and consecutive_closed_sec >= 3.0:
            detected_risk = "CRITICAL"
            trigger_reason = "Prolonged abnormal head slump with eye closure"

        # Rule HIGH-1: Sustained drowsiness ratio above threshold with verified data quality
        elif data_quality_ok and drowsiness_ratio >= HIGH_RISK_DROWSINESS_RATIO:
            detected_risk = "HIGH"
            trigger_reason = f"Sustained drowsiness ratio ({int(drowsiness_ratio * 100)}%) across rolling {int(ROLLING_WINDOW_SECONDS)}s window"
        # Rule HIGH-2: Consecutive eye closure meeting high-risk threshold
        elif consecutive_closed_sec >= HIGH_RISK_CONSECUTIVE_CLOSURE_SEC:
            detected_risk = "HIGH"
            trigger_reason = f"Consecutive eye closure of {consecutive_closed_sec:.1f}s"
        # Rule HIGH-3: Repeated drowsiness events with elevated ratio
        elif recent_drowsiness_count >= HIGH_RISK_MIN_DROWSINESS_EVENTS and (drowsiness_ratio >= 0.20 or consecutive_closed_sec >= 1.5):
            detected_risk = "HIGH"
            trigger_reason = f"{recent_drowsiness_count} repeated drowsiness events with elevated closure ratio in rolling window"
        # Rule HIGH-4: Drowsiness event combined with head slump
        elif recent_drowsiness_count >= 1 and posture in ("HEAD_DOWN", "LAYING_SIDEWAYS"):
            detected_risk = "HIGH"
            trigger_reason = "Drowsiness incident combined with abnormal head-down posture"

        # Check for MODERATE (ordinary evidence accumulation, NO urgent alert)
        elif drowsiness_ratio >= 0.15 or status_label in ("Yawning", "Phone detected", "Head down"):
            detected_risk = "MODERATE"

        # 4. Handle State Transitions & Deduplication
        if detected_risk in ("HIGH", "CRITICAL"):
            state.normal_streak_seconds = 0.0

            # Incident Deduplication Check
            if state.active_alert_id:
                # Escalation from HIGH -> CRITICAL
                if ESCALATION_ENABLED and state.active_risk_level == "HIGH" and detected_risk == "CRITICAL":
                    logger.warning(f"[RISK ESCALATION] Driver {driver_id} escalated from HIGH to CRITICAL risk.")
                    # Mark previous alert escalated/superseded
                    resolve_urgent_alert(state.active_alert_id, "ESCALATED")
                    return cls._create_and_dispatch_alert(
                        driver_id=driver_id,
                        vehicle_id=vehicle_id,
                        risk_level="CRITICAL",
                        alert_type="CRITICAL_SAFETY_ESCALATION",
                        trigger_reason=trigger_reason,
                        evidence=evidence_dict,
                        state=state
                    )
                else:
                    # Same incident continues: update evidence, DO NOT duplicate notification
                    return None
            else:
                # Brand new high/critical incident
                alert_type = "CRITICAL_HAZARD" if detected_risk == "CRITICAL" else "SUSTAINED_DROWSINESS"
                return cls._create_and_dispatch_alert(
                    driver_id=driver_id,
                    vehicle_id=vehicle_id,
                    risk_level=detected_risk,
                    alert_type=alert_type,
                    trigger_reason=trigger_reason,
                    evidence=evidence_dict,
                    state=state
                )

        else:
            # Driver is in LOW or MODERATE state
            if state.active_alert_id:
                # Accumulate recovery time if driver is normal / attentive
                if status_label in ("Attentive", "Normal", "Monitoring running normally") and consecutive_closed_sec == 0:
                    state.normal_streak_seconds += elapsed_since_last
                    if state.normal_streak_seconds >= RECOVERY_STREAK_SECONDS:
                        # Driver has safely recovered!
                        recovered_id = state.active_alert_id
                        resolve_urgent_alert(recovered_id, "RECOVERED")
                        state.active_alert_id = None
                        state.active_risk_level = None
                        state.normal_streak_seconds = 0.0
                        logger.info(f"[INCIDENT RECOVERED] Driver {driver_id} sustained {RECOVERY_STREAK_SECONDS}s alert behavior. Incident closed.")

        return None

    @classmethod
    def evaluate_event(cls, event_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluates a completed safety event (from /api/events).
        Single yawning or phone detections NEVER independently trigger urgent alerts.
        Extreme critical duration (e.g. continuous eye closure >= 4.5s) can trigger CRITICAL alert.
        """
        evt_type = (event_dict.get("event_type") or "").upper()
        severity = (event_dict.get("severity") or "WARNING").upper()
        duration = float(event_dict.get("duration") or 0.0)
        driver_id = event_dict.get("driver_id", "DRV001")
        vehicle_id = event_dict.get("vehicle_id", "VEH001")

        # Explicit rule: single yawn or phone detection MUST NOT independently trigger urgent alert
        if "YAWN" in evt_type or "PHONE" in evt_type:
            return None

        state = cls.get_driver_state(driver_id)

        # Immediate Critical Safety Rule: prolonged severe drowsiness closure
        if "DROWSINESS" in evt_type and duration >= CRITICAL_RISK_CONTINUOUS_CLOSURE_SEC:
            if not state.active_alert_id or (ESCALATION_ENABLED and state.active_risk_level == "HIGH"):
                evidence = {
                    "event_id": event_dict.get("event_id"),
                    "duration": duration,
                    "event_type": evt_type,
                    "severity": severity,
                    "metrics": event_dict.get("metrics", {})
                }
                return cls._create_and_dispatch_alert(
                    driver_id=driver_id,
                    vehicle_id=vehicle_id,
                    risk_level="CRITICAL",
                    alert_type="EXTREME_EYE_CLOSURE",
                    trigger_reason=f"Severe uninterrupted eye closure of {duration:.1f}s",
                    evidence=evidence,
                    state=state
                )

        return None

    @classmethod
    def _create_and_dispatch_alert(
        cls,
        driver_id: str,
        vehicle_id: str,
        risk_level: str,
        alert_type: str,
        trigger_reason: str,
        evidence: Dict[str, Any],
        state: DriverRiskState
    ) -> Dict[str, Any]:
        """Creates the deterministic alert, persists it, updates state, and dispatches via WebSocket."""
        now = datetime.now(timezone.utc)
        alert_id = f"alt_{uuid.uuid4().hex[:8]}"

        # Deterministic evidence explanation
        ratio_pct = int(float(evidence.get("drowsiness_ratio") or 0.0) * 100)
        closed_sec = float(evidence.get("consecutive_closed_sec") or evidence.get("duration") or 0.0)

        if risk_level == "CRITICAL":
            explanation = f"CRITICAL: {trigger_reason}. Driver unresponsiveness detected. Immediate vehicle intervention required."
            recommendations = [
                "Contact driver immediately via audio alert or phone",
                "Direct vehicle to the nearest emergency stopping location",
                "Dispatch safety supervisor if unresponsive"
            ]
        else:
            explanation = f"HIGH RISK: {trigger_reason}. Rolling drowsiness ratio is {ratio_pct}% with sustained eye closure."
            recommendations = [
                "Issue a direct voice prompt to driver",
                "Require an immediate 15-minute rest stop",
                "Track upcoming driving telemetry closely"
            ]

        alert_dict = {
            "alert_id": alert_id,
            "driver_id": driver_id,
            "vehicle_id": vehicle_id,
            "risk_level": risk_level,
            "alert_type": alert_type,
            "timestamp": now.isoformat(),
            "trigger_reason": trigger_reason,
            "evidence": evidence,
            "explanation": explanation,
            "recommendations": recommendations,
            "status": "ACTIVE"
        }

        # 1. Persist to MongoDB
        saved = save_urgent_alert(alert_dict)

        # 2. Update memory state for deduplication
        state.active_alert_id = alert_id
        state.active_risk_level = risk_level
        state.incident_start_time = now
        state.last_alert_time = now
        state.normal_streak_seconds = 0.0

        logger.warning(
            f"[{risk_level} ALERT EMITTED] ID: {alert_id} | Driver: {driver_id} | "
            f"Type: {alert_type} | Reason: {trigger_reason}"
        )

        # 3. Asynchronously broadcast over WebSocket without delay
        def _broadcast():
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        manager.broadcast({
                            "type": "URGENT_SAFETY_ALERT",
                            "alert": saved
                        }),
                        loop
                    )
            except Exception as ex:
                logger.debug(f"WebSocket alert broadcast note: {ex}")

        threading.Thread(target=_broadcast, daemon=True).start()

        # 4. Asynchronously enrich explanation using Gemma (without blocking or delaying deterministic alert)
        def _enrich_with_gemma(target_alert: Dict[str, Any]):
            try:
                res = _gemma.explain_urgent_alert(target_alert)
                if res.get("status") == "success" and res.get("explanation"):
                    update_alert_explanation(
                        alert_id=target_alert["alert_id"],
                        explanation=res["explanation"],
                        recommendations=res.get("recommendations")
                    )
                    # Broadcast updated explanation
                    def _broadcast_enrichment():
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    manager.broadcast({
                                        "type": "ALERT_EXPLANATION_UPDATED",
                                        "alert_id": target_alert["alert_id"],
                                        "explanation": res["explanation"],
                                        "recommendations": res.get("recommendations")
                                    }),
                                    loop
                                )
                        except Exception:
                            pass
                    threading.Thread(target=_broadcast_enrichment, daemon=True).start()
                    logger.info(f"Gemma enriched explanation applied to alert {target_alert['alert_id']}")
            except Exception as err:
                logger.debug(f"Gemma enrichment worker notice: {err}")

        threading.Thread(target=_enrich_with_gemma, args=(saved,), daemon=True).start()

        return saved

    @classmethod
    def reset_state(cls, driver_id: Optional[str] = None):
        """Resets in-memory state tracking (useful for unit tests)."""
        with cls._lock:
            if driver_id:
                if driver_id in cls._states:
                    del cls._states[driver_id]
            else:
                cls._states.clear()
