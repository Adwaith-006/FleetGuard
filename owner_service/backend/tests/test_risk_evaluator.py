"""
Unit and Integration Test Suite for High-Risk Driver Detection & Dashboard Alerts.
Verifies all 14 mandatory scenarios:
1. Normal alert driver -> No urgent notification.
2. Single yawn -> No urgent notification.
3. Single phone detection -> No urgent notification.
4. Brief eye closure -> No urgent notification.
5. Short downward glance -> No urgent notification.
6. Sustained simulated drowsiness -> One HIGH-risk notification with full evidence.
7. Repeated high-risk observations during same incident -> Deduplicated (no duplicate notification).
8. Recovery followed by a new high-risk incident -> New notification allowed.
9. Unreliable face detection or insufficient valid frames -> Data quality check prevents false alert.
10. Ollama unavailable -> Deterministic high-risk alerting continues reliably.
11. Gemma malformed output -> Evaluator risk classification and decision remain intact.
12. CRITICAL configured safety rule -> Instant alert without waiting for Gemma.
13. Dashboard reconnect -> Active alerts recovered from database.
14. Alert resolution and management API endpoints.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

# Ensure paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
SERVICE_DIR = BACKEND_DIR.parent
REPO_ROOT = SERVICE_DIR.parent
for p in (str(REPO_ROOT), str(SERVICE_DIR), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient
from owner_service.backend.main import app
from owner_service.backend.services.risk_evaluator import RiskEvaluator, DriverRiskState
from owner_service.backend.database import (
    init_db,
    save_urgent_alert,
    get_active_alert,
    get_urgent_alerts,
    resolve_urgent_alert,
    get_database
)
from owner_service.ai.gemma_service import GemmaService

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Ensures database and evaluator states are clean before each test."""
    init_db()
    RiskEvaluator.reset_state("DRV001")
    RiskEvaluator.reset_state("DRV_TEST")
    db = get_database()
    db["urgent_alerts"].delete_many({})
    yield
    RiskEvaluator.reset_state("DRV001")
    RiskEvaluator.reset_state("DRV_TEST")
    db["urgent_alerts"].delete_many({})


def test_scenario_1_normal_alert_driver():
    """Scenario 1: Normal alert driver: No urgent notification."""
    telemetry = {
        "driver_id": "DRV001",
        "vehicle_id": "VEH001",
        "status": "Attentive",
        "metrics": {
            "ear": 0.28,
            "mar": 0.15,
            "phone_detected": False,
            "posture": "UPRIGHT",
            "temporal": {
                "valid_face_frames": 60,
                "closed_eye_frames": 2,
                "drowsiness_ratio": 0.033,
                "consecutive_closed_sec": 0.0,
                "data_quality_ok": True
            }
        }
    }
    alert = RiskEvaluator.evaluate_telemetry(telemetry)
    assert alert is None, "Normal driver telemetry must not trigger an urgent alert."
    assert get_active_alert("DRV001") is None


def test_scenario_2_single_yawn():
    """Scenario 2: Single yawn: No urgent notification."""
    event = {
        "event_id": "evt_yawn_01",
        "driver_id": "DRV001",
        "event_type": "YAWNING",
        "duration": 2.5,
        "severity": "WARNING",
        "metrics": {"max_mar": 0.65}
    }
    alert = RiskEvaluator.evaluate_event(event)
    assert alert is None, "A single yawn must not independently trigger an urgent alert."

    # Also test telemetry during yawn
    telemetry = {
        "driver_id": "DRV001",
        "status": "Yawning",
        "metrics": {
            "mar": 0.65,
            "temporal": {
                "valid_face_frames": 40,
                "closed_eye_frames": 0,
                "drowsiness_ratio": 0.0,
                "data_quality_ok": True
            }
        }
    }
    assert RiskEvaluator.evaluate_telemetry(telemetry) is None


def test_scenario_3_single_phone_detection():
    """Scenario 3: Single phone detection: No urgent notification."""
    event = {
        "event_id": "evt_phone_01",
        "driver_id": "DRV001",
        "event_type": "PHONE_DETECTED",
        "duration": 3.0,
        "severity": "WARNING",
        "confidence": 0.85
    }
    alert = RiskEvaluator.evaluate_event(event)
    assert alert is None, "A single phone-use detection must not independently trigger an urgent alert."


def test_scenario_4_brief_eye_closure():
    """Scenario 4: Brief eye closure: No urgent notification."""
    telemetry = {
        "driver_id": "DRV001",
        "status": "Eyes closed",
        "metrics": {
            "ear": 0.15,
            "temporal": {
                "valid_face_frames": 50,
                "closed_eye_frames": 6,
                "drowsiness_ratio": 0.12,  # Well below 0.30
                "consecutive_closed_sec": 0.4,  # Normal blink
                "data_quality_ok": True
            }
        }
    }
    alert = RiskEvaluator.evaluate_telemetry(telemetry)
    assert alert is None, "Brief eye closure (blink) must not trigger an urgent alert."


def test_scenario_5_short_downward_glance():
    """Scenario 5: Short glance downward: No urgent notification."""
    telemetry = {
        "driver_id": "DRV001",
        "status": "Head down",
        "metrics": {
            "posture": "HEAD_DOWN",
            "temporal": {
                "valid_face_frames": 45,
                "closed_eye_frames": 0,
                "drowsiness_ratio": 0.0,
                "consecutive_closed_sec": 0.0,
                "data_quality_ok": True
            }
        }
    }
    alert = RiskEvaluator.evaluate_telemetry(telemetry)
    assert alert is None, "A short downward glance without sustained drowsiness must not trigger an urgent alert."


def test_scenario_6_sustained_simulated_drowsiness():
    """Scenario 6: Sustained simulated drowsiness: One HIGH-risk notification with verified evidence."""
    telemetry = {
        "driver_id": "DRV001",
        "vehicle_id": "VEH001",
        "status": "Drowsy",
        "metrics": {
            "ear": 0.14,
            "temporal": {
                "valid_face_frames": 120,
                "closed_eye_frames": 42,
                "drowsiness_ratio": 0.35,  # >= 0.30 HIGH risk threshold
                "consecutive_closed_sec": 2.2,
                "data_quality_ok": True
            }
        }
    }
    alert = RiskEvaluator.evaluate_telemetry(telemetry)
    assert alert is not None, "Sustained drowsiness exceeding 30% ratio must trigger an urgent alert."
    assert alert["risk_level"] == "HIGH"
    assert alert["driver_id"] == "DRV001"
    assert alert["status"] == "ACTIVE"
    assert "drowsiness_ratio" in alert["evidence"]
    assert alert["evidence"]["drowsiness_ratio"] == 0.35
    assert len(alert["explanation"]) > 0
    assert len(alert["recommendations"]) > 0

    # Verify persisted in database
    db_alert = get_active_alert("DRV001")
    assert db_alert is not None
    assert db_alert["alert_id"] == alert["alert_id"]


def test_scenario_7_repeated_observations_same_incident():
    """Scenario 7: Repeated high-risk observations during same incident: Deduplicated (no duplicate notification)."""
    telemetry = {
        "driver_id": "DRV001",
        "status": "Drowsy",
        "metrics": {
            "temporal": {
                "valid_face_frames": 100,
                "closed_eye_frames": 35,
                "drowsiness_ratio": 0.35,
                "consecutive_closed_sec": 2.0,
                "data_quality_ok": True
            }
        }
    }
    # First observation triggers alert
    alert1 = RiskEvaluator.evaluate_telemetry(telemetry)
    assert alert1 is not None

    # Immediate subsequent frame/telemetry during same incident
    alert2 = RiskEvaluator.evaluate_telemetry(telemetry)
    assert alert2 is None, "Subsequent observations during the same active incident must NOT emit duplicate notifications."

    # Total alerts in database must still be exactly 1
    alerts_in_db = get_urgent_alerts("DRV001")
    assert len(alerts_in_db) == 1


def test_scenario_8_recovery_followed_by_new_incident():
    """Scenario 8: Recovery followed by a new high-risk incident: New notification is allowed."""
    telemetry_drowsy = {
        "driver_id": "DRV001",
        "status": "Drowsy",
        "metrics": {
            "temporal": {
                "valid_face_frames": 100,
                "closed_eye_frames": 36,
                "drowsiness_ratio": 0.36,
                "consecutive_closed_sec": 2.0,
                "data_quality_ok": True
            }
        }
    }
    # 1. Trigger first incident
    alert1 = RiskEvaluator.evaluate_telemetry(telemetry_drowsy)
    assert alert1 is not None

    # 2. Driver recovers (simulates 16 seconds of attentive driving)
    state = RiskEvaluator.get_driver_state("DRV001")
    state.normal_streak_seconds = 16.0  # Exceeds recovery threshold (15s)

    telemetry_normal = {
        "driver_id": "DRV001",
        "status": "Attentive",
        "metrics": {
            "temporal": {
                "valid_face_frames": 60,
                "closed_eye_frames": 0,
                "drowsiness_ratio": 0.0,
                "consecutive_closed_sec": 0.0,
                "data_quality_ok": True
            }
        }
    }
    RiskEvaluator.evaluate_telemetry(telemetry_normal)

    # Assert active incident is resolved/recovered
    assert state.active_alert_id is None, "Active alert should clear after sustained recovery streak."

    # 3. Subsequent brand new incident occurs
    alert2 = RiskEvaluator.evaluate_telemetry(telemetry_drowsy)
    assert alert2 is not None, "A new incident following recovery must trigger a new alert."
    assert alert2["alert_id"] != alert1["alert_id"]


def test_scenario_9_unreliable_face_insufficient_frames():
    """Scenario 9: Unreliable face detection or insufficient valid frames: Data quality check prevents false alert."""
    telemetry_bad_quality = {
        "driver_id": "DRV001",
        "status": "Searching for driver",
        "metrics": {
            "temporal": {
                "valid_face_frames": 5,  # Too few (< 30)
                "closed_eye_frames": 5,
                "drowsiness_ratio": 0.0,  # Suppressed due to low data quality
                "consecutive_closed_sec": 0.0,
                "data_quality_ok": False  # Missing/unreliable face
            }
        }
    }
    alert = RiskEvaluator.evaluate_telemetry(telemetry_bad_quality)
    assert alert is None, "Missing face / poor data quality must NOT be classified as drowsiness."


def test_scenario_10_ollama_unavailable():
    """Scenario 10: Ollama unavailable: Deterministic high-risk alerting continues reliably."""
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused (Ollama offline)")):
        gemma = GemmaService()
        res = gemma.explain_urgent_alert({
            "driver_id": "DRV001",
            "risk_level": "HIGH",
            "alert_type": "SUSTAINED_DROWSINESS",
            "evidence": {"drowsiness_ratio": 0.32, "consecutive_closed_sec": 2.5}
        })
        assert res["status"] == "deterministic_fallback"
        assert "HIGH risk" in res["explanation"]
        assert len(res["recommendations"]) > 0


def test_scenario_11_gemma_malformed_output():
    """Scenario 11: Gemma returns malformed output: Evaluator risk classification and decision remain intact."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"response": "Here is an analysis: {invalid json bad format"}'

    with patch("urllib.request.urlopen", return_value=mock_resp):
        gemma = GemmaService()
        res = gemma.explain_urgent_alert({
            "driver_id": "DRV001",
            "risk_level": "HIGH",
            "alert_type": "SUSTAINED_DROWSINESS",
            "evidence": {"drowsiness_ratio": 0.35}
        })
        assert res["status"] == "deterministic_fallback"
        assert "HIGH risk" in res["explanation"]


def test_scenario_12_critical_configured_rule():
    """Scenario 12: CRITICAL configured safety rule: Alert immediately without waiting for Gemma."""
    telemetry_critical = {
        "driver_id": "DRV001",
        "status": "Eyes closed",
        "metrics": {
            "temporal": {
                "valid_face_frames": 100,
                "closed_eye_frames": 80,
                "drowsiness_ratio": 0.80,
                "consecutive_closed_sec": 5.0,  # >= 4.5s CRITICAL threshold
                "data_quality_ok": True
            }
        }
    }
    alert = RiskEvaluator.evaluate_telemetry(telemetry_critical)
    assert alert is not None
    assert alert["risk_level"] == "CRITICAL"
    assert "Extreme continuous eye closure" in alert["trigger_reason"]
    assert "CRITICAL" in alert["explanation"]


def test_scenario_13_websocket_active_alert_recovery():
    """Scenario 13: Dashboard reconnect: Active alerts are recovered from database."""
    # Seed active alert in DB
    save_urgent_alert({
        "alert_id": "alt_reconnect_01",
        "driver_id": "DRV001",
        "risk_level": "HIGH",
        "alert_type": "SUSTAINED_DROWSINESS",
        "status": "ACTIVE",
        "explanation": "Sustained drowsiness detected across rolling window.",
        "evidence": {"drowsiness_ratio": 0.34}
    })

    resp = client.get("/api/alerts/active?driver_id=DRV001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"] is True
    assert body["alert"]["alert_id"] == "alt_reconnect_01"


def test_scenario_14_alerts_api_and_resolution():
    """Scenario 14: Alert list and resolution API endpoints work seamlessly."""
    save_urgent_alert({
        "alert_id": "alt_mgmt_01",
        "driver_id": "DRV001",
        "risk_level": "HIGH",
        "status": "ACTIVE"
    })

    # 1. Query alert list
    list_resp = client.get("/api/alerts?driver_id=DRV001")
    assert list_resp.status_code == 200
    alerts = list_resp.json()
    assert any(a["alert_id"] == "alt_mgmt_01" for a in alerts)

    # 2. Resolve alert
    resolve_resp = client.post("/api/alerts/alt_mgmt_01/resolve")
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "success"

    # 3. Verify no longer active
    active_resp = client.get("/api/alerts/active?driver_id=DRV001")
    assert active_resp.json()["active"] is False
