"""
Automated unit and integration tests for Owner Management Service backend.
Tests event ingestion, MongoDB persistence, status classification,
FastAPI REST endpoints, WebSocket broadcast logic, and Gemma LLM offline handling.
"""

import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
SERVICE_DIR = BACKEND_DIR.parent
REPO_ROOT = SERVICE_DIR.parent
for p in (str(REPO_ROOT), str(SERVICE_DIR), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import mongomock
from fastapi.testclient import TestClient

from shared.event_schema import EventStatusClassifier
from owner_service.ai.gemma_service import GemmaService
from owner_service.backend.database import (
    set_client,
    init_db,
    save_event,
    get_all_events,
    get_event_by_id,
    update_event_explanation,
    save_ai_analysis,
    get_all_analyses,
    get_drivers_status,
    get_driver_by_id,
    update_driver_status
)
from owner_service.backend.services.event_service import EventService
from owner_service.backend.websocket import ConnectionManager
from owner_service.backend.main import app


@pytest.fixture(autouse=True)
def setup_mock_mongodb():
    """Sets up a fresh in-memory mongomock client for each test."""
    mock_client = mongomock.MongoClient()
    set_client(mock_client)
    init_db()
    yield mock_client
    set_client(None)


# =====================================================================
# 1. MongoDB Persistence and Retrieval
# =====================================================================
def test_mongodb_persistence_and_retrieval():
    """Validates inserting, querying, and updating events in MongoDB."""
    sample_event = {
        "event_id": "evt_test_001",
        "driver_id": "DRV_TEST",
        "driver_name": "Test Driver",
        "vehicle_id": "VEH_TEST",
        "vehicle_no": "Rig 101",
        "session_id": "sess_unit_test",
        "event_type": "DROWSINESS",
        "start_time": "2026-10-26T12:00:00Z",
        "end_time": "2026-10-26T12:00:03Z",
        "timestamp": "2026-10-26T12:00:03Z",
        "duration": 3.0,
        "severity": "CRITICAL",
        "status": "HIGH_RISK",
        "confidence": 0.95,
        "metrics": {"avg_ear": 0.18, "min_ear": 0.15}
    }

    # Save event
    saved = save_event(sample_event)
    assert saved["event_id"] == "evt_test_001"
    assert saved["duration"] == 3.0
    assert saved["metrics"]["avg_ear"] == 0.18

    # Retrieve by ID
    retrieved = get_event_by_id("evt_test_001")
    assert retrieved is not None
    assert retrieved["driver_id"] == "DRV_TEST"
    assert retrieved["severity"] == "CRITICAL"

    # List events with pagination and filters
    all_events = get_all_events(limit=10, driver_id="DRV_TEST")
    assert len(all_events) >= 1
    assert any(e["event_id"] == "evt_test_001" for e in all_events)

    # Filter by non-existent driver returns empty
    empty_events = get_all_events(limit=10, driver_id="DRV_NONEXISTENT")
    assert len(empty_events) == 0

    # Update explanation
    update_event_explanation("evt_test_001", "Gemma test explanation: Driver showed severe eyelid closure.")
    updated = get_event_by_id("evt_test_001")
    assert "severe eyelid closure" in updated["explanation"]


def test_ai_analysis_persistence():
    """Validates saving and querying structured Gemma analyses in MongoDB."""
    analysis_record = {
        "analysis_id": "ana_test_001",
        "event_id": "evt_test_001",
        "driver_id": "DRV_TEST",
        "model_used": "gemma4:e4b",
        "summary": "Driver showed prolonged eyelid closure indicative of microsleep.",
        "risk_level": "CRITICAL",
        "supporting_evidence": ["Eye closure 3.0s", "Avg EAR 0.18"],
        "recommended_action": "Require driver to stop at nearest safe parking.",
        "evidence_event_ids": ["evt_test_001"]
    }
    saved = save_ai_analysis(analysis_record)
    assert saved["analysis_id"] == "ana_test_001"
    assert saved["risk_level"] == "CRITICAL"

    analyses = get_all_analyses(event_id="evt_test_001")
    assert len(analyses) == 1
    assert analyses[0]["analysis_id"] == "ana_test_001"


# =====================================================================
# 2. Status Classification Validation
# =====================================================================
def test_status_classification():
    """Validates objective status classification for different events."""
    assert EventStatusClassifier.classify_status("DROWSINESS", duration=1.0) == "OBSERVED"
    assert EventStatusClassifier.classify_status("DROWSINESS", duration=2.0) == "DROWSINESS_DETECTED"
    assert EventStatusClassifier.classify_status("DROWSINESS", duration=3.5, severity="CRITICAL") == "HIGH_RISK"
    assert EventStatusClassifier.classify_status("YAWNING", duration=2.5) == "ATTENTION_REQUIRED"
    assert EventStatusClassifier.classify_status("PHONE_DETECTED", duration=0.8) == "BRIEF"
    assert EventStatusClassifier.classify_status("PHONE_DETECTED", duration=3.0) == "ATTENTION_REQUIRED"


# =====================================================================
# 3. Gemma API Failure Handling (Offline Tolerance)
# =====================================================================
def test_gemma_offline_handling():
    """Validates that GemmaService does not crash or raise exceptions when Ollama is offline."""
    gemma = GemmaService(ollama_url="http://127.0.0.1:59999", timeout=0.5)

    health = gemma.check_health()
    assert health["available"] is False
    assert health["ollama_running"] is False
    assert "offline" in health["message"].lower() or "unreachable" in health["message"].lower()

    # Attempting explanation should return clean dictionary with status 'unavailable'
    result = gemma.explain_event({
        "event_id": "evt_dummy",
        "event_type": "DROWSINESS",
        "duration": 2.5,
        "severity": "WARNING"
    })
    assert result["status"] == "unavailable"
    assert len(result["explanation"]) > 0
    assert "127.0.0.1" not in result["explanation"]
    assert "ollama" not in result["explanation"].lower()
    assert "mongodb" not in result["explanation"].lower()


# =====================================================================
# 4. Gemma Mocked Explanation Success
# =====================================================================
def test_gemma_mocked_explanation():
    """Validates Gemma response parsing when Ollama responds with structured JSON."""
    gemma = GemmaService(ollama_url="http://localhost:11434")

    mock_resp_json = {
        "response": '{"summary": "Driver had severe eyelid closure.", "risk_level": "CRITICAL", "supporting_evidence": ["EAR below 0.20 for 3s"], "recommended_action": "Immediate rest stop."}'
    }
    mock_response = MagicMock()
    mock_response.status = 200
    import json
    mock_response.read.return_value = json.dumps(mock_resp_json).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = gemma.analyze_event_structured({
            "event_id": "evt_mock_01",
            "event_type": "DROWSINESS",
            "duration": 3.0,
            "severity": "CRITICAL",
            "metrics": {"avg_ear": 0.17}
        })
        assert result["status"] == "success"
        assert result["risk_level"] == "CRITICAL"
        assert "severe eyelid closure" in result["summary"]


# =====================================================================
# 5. FastAPI Endpoints Testing (GET /api/health, /drivers, /events, POST)
# =====================================================================
def test_fastapi_health_endpoint():
    """Tests GET /api/health endpoint returns backend and MongoDB status."""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "ai" in data


def test_fastapi_drivers_endpoint():
    """Tests GET /api/drivers returns driver list."""
    client = TestClient(app)
    response = client.get("/api/drivers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(d["driver_id"] == "DRV001" for d in data)


def test_fastapi_events_crud_and_validation():
    """Tests POST /api/events, GET /api/events, and GET /api/events/{id}."""
    client = TestClient(app)

    payload = {
        "event_id": "evt_api_test_100",
        "driver_id": "DRV001",
        "driver_name": "Prototype Driver",
        "vehicle_id": "VEH001",
        "vehicle_no": "Cabin Rig",
        "session_id": "sess_api_test",
        "event_type": "DROWSINESS",
        "start_time": "2026-10-26T12:00:00Z",
        "end_time": "2026-10-26T12:00:02Z",
        "timestamp": "2026-10-26T12:00:02Z",
        "duration": 2.0,
        "severity": "WARNING",
        "confidence": 0.88,
        "metrics": {"avg_ear": 0.19}
    }

    # 1. POST /api/events
    post_res = client.post("/api/events", json=payload)
    assert post_res.status_code == 201
    post_data = post_res.json()
    assert post_data["status"] == "success"
    assert post_data["event"]["event_id"] == "evt_api_test_100"

    # 2. GET /api/events with filter
    list_res = client.get("/api/events?driver_id=DRV001&limit=10")
    assert list_res.status_code == 200
    events = list_res.json()
    assert any(e["event_id"] == "evt_api_test_100" for e in events)

    # 3. GET /api/events/{id}
    detail_res = client.get("/api/events/evt_api_test_100")
    assert detail_res.status_code == 200
    assert detail_res.json()["event_id"] == "evt_api_test_100"

    # 4. GET non-existent event returns 404
    not_found_res = client.get("/api/events/evt_non_existent")
    assert not_found_res.status_code == 404


def test_fastapi_ai_analyze_endpoint():
    """Tests POST /api/ai/analyze returns structured analysis."""
    client = TestClient(app)

    # Seed an event first
    save_event({
        "event_id": "evt_for_ai",
        "driver_id": "DRV001",
        "event_type": "DROWSINESS",
        "duration": 3.0,
        "severity": "CRITICAL",
        "metrics": {"avg_ear": 0.16}
    })

    with patch.object(EventService, "analyze_event_now", return_value={
        "status": "success",
        "analysis_id": "ana_mock_001",
        "event_id": "evt_for_ai",
        "summary": "Mocked Gemma: Severe eye closure.",
        "risk_level": "CRITICAL",
        "recommended_action": "Rest immediately."
    }):
        res = client.post("/api/ai/analyze", json={"event_id": "evt_for_ai"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["event_id"] == "evt_for_ai"


# =====================================================================
# 6. WebSocket Connection Manager Logic
# =====================================================================
def test_websocket_manager_broadcast():
    """Validates WebSocket connection registration and broadcasting without crashing."""
    import asyncio

    async def _test():
        manager = ConnectionManager()
        assert len(manager.active_connections) == 0

        mock_ws = MagicMock()
        # Test safe broadcast when no clients are connected
        await manager.broadcast({"type": "TEST", "data": 123})

        # Test disconnect on non-registered socket
        manager.disconnect(mock_ws)
        assert len(manager.active_connections) == 0

    asyncio.run(_test())


# =====================================================================
# 7. Idempotency & Duplicate Prevention on Network Retries
# =====================================================================
def test_idempotent_event_persistence_and_retry_protection():
    """
    Validates that delivering the exact same event multiple times (simulating network retries)
    does not create duplicate records or double-increment driver violation counters.
    """
    retry_event = {
        "event_id": "evt_retry_idempotent_01",
        "driver_id": "DRV001",
        "event_type": "DROWSINESS",
        "duration": 2.5,
        "severity": "WARNING",
        "status": "DROWSINESS_DETECTED",
        "metrics": {"avg_ear": 0.17}
    }

    # Initial delivery
    save_event(retry_event)
    driver_after_first = get_driver_by_id("DRV001")
    initial_total = driver_after_first.get("total_events", 0)
    initial_drowsy = driver_after_first.get("drowsiness_count", 0)

    # Simulated network retry of the exact same event
    save_event(retry_event)
    driver_after_retry = get_driver_by_id("DRV001")

    # Violation counts must NOT increase on duplicate delivery
    assert driver_after_retry.get("total_events") == initial_total
    assert driver_after_retry.get("drowsiness_count") == initial_drowsy

    # Only 1 document should exist in drowsiness_events
    events = get_all_events(driver_id="DRV001")
    matching = [e for e in events if e.get("event_id") == "evt_retry_idempotent_01"]
    assert len(matching) == 1


# =====================================================================
# 8. Yawning Event Category Counter
# =====================================================================
def test_yawning_event_counter_increment():
    """Validates that confirmed yawning events increment driver yawning_count correctly."""
    driver_before = get_driver_by_id("DRV001")
    prior_yawn = driver_before.get("yawning_count", 0)

    yawn_event = {
        "event_id": "evt_yawn_test_99",
        "driver_id": "DRV001",
        "event_type": "YAWNING",
        "duration": 2.2,
        "severity": "WARNING",
        "metrics": {"max_mar": 0.58}
    }
    save_event(yawn_event)

    driver_after = get_driver_by_id("DRV001")
    assert driver_after.get("yawning_count") == prior_yawn + 1


# =====================================================================
# 9. Driver By ID and Live Status Endpoints
# =====================================================================
def test_fastapi_driver_by_id_and_status_endpoints():
    """Tests GET /api/drivers/{driver_id} and POST /api/drivers/status."""
    client = TestClient(app)

    # 1. GET valid driver
    res = client.get("/api/drivers/DRV001")
    assert res.status_code == 200
    driver_data = res.json()
    assert driver_data["driver_id"] == "DRV001"

    # 2. GET non-existent driver returns 404
    not_found = client.get("/api/drivers/DRV_DOES_NOT_EXIST")
    assert not_found.status_code == 404

    # 3. POST /api/drivers/status (live status update)
    status_payload = {
        "driver_id": "DRV001",
        "status": "Drowsy",
        "monitoring_state": "Monitoring running normally",
        "metrics": {"ear": 0.18, "mar": 0.22, "posture": "UPRIGHT"}
    }
    status_res = client.post("/api/drivers/status", json=status_payload)
    assert status_res.status_code == 200
    res_body = status_res.json()
    assert res_body["status"] == "success"
    assert res_body["driver"]["status"] == "Drowsy"
    assert res_body["driver"]["monitoring_state"] == "Monitoring running normally"


# =====================================================================
# 10. Malformed and Invalid Payload Rejection
# =====================================================================
def test_fastapi_invalid_event_rejection():
    """Validates that malformed or empty payloads are rejected with 422 Unprocessable Entity."""
    client = TestClient(app)

    # Empty event_type
    bad_payload_1 = {
        "event_id": "evt_bad_01",
        "event_type": "",
        "driver_id": "DRV001"
    }
    res1 = client.post("/api/events", json=bad_payload_1)
    assert res1.status_code == 422

    # Whitespace driver_id
    bad_payload_2 = {
        "event_id": "evt_bad_02",
        "event_type": "DROWSINESS",
        "driver_id": "   "
    }
    res2 = client.post("/api/events", json=bad_payload_2)
    assert res2.status_code == 422


# =====================================================================
# 11. WebSocket Broadcast to Connected Clients & Error Isolation
# =====================================================================
def test_websocket_broadcast_delivery_and_error_isolation():
    """
    Validates that WebSocket broadcast delivers to active clients,
    and an error in one client connection does not break transmission to others.
    """
    import asyncio
    from unittest.mock import AsyncMock

    async def _test():
        manager = ConnectionManager()

        # Healthy client 1
        client1 = AsyncMock()
        client1.accept = AsyncMock()
        client1.send_json = AsyncMock()

        # Failing client 2 (raises exception during transmit)
        client2 = AsyncMock()
        client2.accept = AsyncMock()
        client2.send_json = AsyncMock(side_effect=RuntimeError("Socket broken"))

        # Healthy client 3
        client3 = AsyncMock()
        client3.accept = AsyncMock()
        client3.send_json = AsyncMock()

        await manager.connect(client1)
        await manager.connect(client2)
        await manager.connect(client3)

        assert len(manager.active_connections) == 3

        test_msg = {"type": "NEW_SAFETY_EVENT", "event": {"event_id": "evt_ws_broadcast_01"}}
        await manager.broadcast(test_msg)

        # Client 1 and 3 received the message successfully
        client1.send_json.assert_awaited_once_with(test_msg)
        client3.send_json.assert_awaited_once_with(test_msg)

        # Faulty client 2 should be pruned from active connections
        assert client2 not in manager.active_connections
        assert len(manager.active_connections) == 2

    asyncio.run(_test())


# =====================================================================
# 16. Driver Safety AI Q&A and Structured Gemma Inference
# =====================================================================
def test_ask_driver_safety_question_with_mocked_ollama():
    """Tests POST /api/ai/ask with mocked Ollama generating validated JSON response."""
    test_client = TestClient(app)

    # Seed events for DRV001
    save_event({
        "event_id": "evt_ai_test_01",
        "driver_id": "DRV001",
        "event_type": "DROWSINESS",
        "duration": 2.5,
        "severity": "CRITICAL",
        "metrics": {"avg_ear": 0.17}
    })
    save_event({
        "event_id": "evt_ai_test_02",
        "driver_id": "DRV001",
        "event_type": "YAWNING",
        "duration": 3.0,
        "severity": "WARNING",
        "metrics": {"avg_mar": 0.62}
    })

    mock_ollama_resp = {
        "response": json.dumps({
            "executive_summary": "Driver exhibits significant fatigue with critical drowsiness and yawning events.",
            "risk_level": "HIGH",
            "key_findings": ["Severe eye closure observed for 2.5s", "Sustained yawning indicates progressive fatigue"],
            "recommendations": ["Mandatory 30-minute rest break", "Cabin ventilation check"],
            "answer": "Telemetry reveals multiple fatigue indicators requiring immediate driver rest."
        })
    }

    mock_resp_obj = MagicMock()
    mock_resp_obj.status = 200
    mock_resp_obj.read.return_value = json.dumps(mock_ollama_resp).encode("utf-8")
    mock_resp_obj.__enter__.return_value = mock_resp_obj

    with patch("urllib.request.urlopen", return_value=mock_resp_obj):
        resp = test_client.post(
            "/api/ai/ask",
            json={
                "driver_id": "DRV001",
                "question": "What are the most frequent violations for this driver?",
                "time_range": "30m"
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["driver_id"] == "DRV001"
    assert data["risk_level"] in ("HIGH", "WARNING")
    assert "telemetry_facts" in data
    assert data["telemetry_facts"]["drowsiness_count"] >= 1
    assert data["telemetry_facts"]["yawning_count"] >= 1
    assert len(data["recommendations"]) >= 1
    assert "analysis_id" in data

    # Verify persistence in MongoDB
    analyses_resp = test_client.get("/api/ai/analyses?driver_id=DRV001")
    assert analyses_resp.status_code == 200
    history = analyses_resp.json()
    assert len(history) >= 1
    assert any(a["analysis_id"] == data["analysis_id"] for a in history)


def test_ask_driver_safety_question_when_ollama_offline():
    """Tests graceful fallback when Ollama is offline: returns factual data without crashing."""
    test_client = TestClient(app)

    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        resp = test_client.post(
            "/api/ai/ask",
            json={
                "driver_id": "DRV001",
                "question": "Why is this driver's safety rating low?",
                "time_range": "30m"
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unavailable"
    assert "Ollama" not in data["answer"]
    assert "MongoDB" not in data["answer"]
    assert "11434" not in data["answer"]
    assert "127.0.0.1" not in data["answer"]
    assert len(data["answer"]) > 10
    assert "telemetry_facts" in data
    assert "safety_score" in data["telemetry_facts"]
    assert len(data["key_findings"]) >= 1


def test_driver_safety_summary_endpoint():
    """Tests POST /api/ai/summary endpoint generating periodic safety reports."""
    test_client = TestClient(app)

    mock_ollama_resp = {
        "response": json.dumps({
            "executive_summary": "Comprehensive driving safety evaluation indicates stable performance with minor fatigue.",
            "risk_level": "MEDIUM",
            "key_findings": ["1 warning yawn observed", "Driver remained responsive"],
            "recommendations": ["Maintain current shift rotations"],
            "answer": "Driver demonstrated acceptable alertness throughout the shift."
        })
    }
    mock_resp_obj = MagicMock()
    mock_resp_obj.status = 200
    mock_resp_obj.read.return_value = json.dumps(mock_ollama_resp).encode("utf-8")
    mock_resp_obj.__enter__.return_value = mock_resp_obj

    with patch("urllib.request.urlopen", return_value=mock_resp_obj):
        resp = test_client.post(
            "/api/ai/summary",
            json={
                "driver_id": "DRV001",
                "time_range": "today"
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["analysis_type"] == "PERIODIC_SUMMARY"
    assert "analysis_id" in data


def test_ask_driver_safety_nonexistent_driver():
    """Tests requesting AI analysis for a completely invalid driver ID returns 404."""
    test_client = TestClient(app)

    resp = test_client.post(
        "/api/ai/ask",
        json={
            "driver_id": "DRV_TOTALLY_UNKNOWN_9999",
            "question": "Analyze safety",
            "time_range": "all"
        }
    )
    assert resp.status_code == 404


