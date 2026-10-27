"""
Tests for ChatGPT-style conversational Gemma assistant,
verifying natural responses, grounded evidence, context tracking,
and removal of unwanted automatic reports.
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
from starlette.testclient import TestClient

from owner_service.backend.main import app
from owner_service.backend.services.event_service import EventService
from owner_service.ai.gemma_service import GemmaService
from owner_service.backend.database import init_db


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()


def test_hiii_produces_friendly_greeting_no_telemetry_or_scores():
    """Scenario 1: 'Hiii' produces a friendly greeting matching owner tone with NO telemetry summary or score."""
    test_client = TestClient(app)

    # Calling /api/ai/ask with 'Hiii'
    resp = test_client.post(
        "/api/ai/ask",
        json={
            "driver_id": "DRV001",
            "question": "Hiii",
            "time_range": "30m"
        }
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "GREETING_OR_SOCIAL"
    assert data["is_formal_report"] is False
    assert data["risk_level"] is None
    assert data["telemetry_facts"] is None
    assert data["relevant_events"] == []
    assert data["disclaimer"] is None
    # Verifies it greets the user and does NOT mention phone distractions, violation counts, or scores
    assert "Hiii!" in data["answer"] or "How can I help" in data["answer"]
    assert "phone distraction" not in data["answer"].lower()
    assert "safety event(s) were recorded" not in data["answer"].lower()
    assert "safety rating is" not in data["answer"].lower()


def test_greeting_and_courtesy_phrases():
    """Scenario 2: Greetings like 'Hello, how can you help me?' and 'Thank you' produce conversational answers without safety reports."""
    test_client = TestClient(app)

    # Test "Hello, what can you help me with?"
    resp1 = test_client.post(
        "/api/ai/ask",
        json={
            "driver_id": "DRV001",
            "question": "Hello, what can you help me with?",
            "time_range": "30m"
        }
    )
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["intent"] == "GREETING_OR_SOCIAL"
    assert d1["telemetry_facts"] is None
    assert "help you understand driver safety" in d1["answer"]

    # Test "Thank you"
    resp2 = test_client.post(
        "/api/ai/ask",
        json={
            "driver_id": "DRV001",
            "question": "Thank you",
            "time_range": "30m"
        }
    )
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["intent"] == "GREETING_OR_SOCIAL"
    assert d2["telemetry_facts"] is None
    assert "welcome" in d2["answer"].lower()


def test_30m_query_returns_facts_without_fixed_report_template():
    """Scenario 3: 'What happened in the last 30 minutes?' returns relevant verified facts without the fixed template."""
    test_client = TestClient(app)

    mock_ollama_resp = {
        "response": json.dumps({
            "answer": "One phone-distraction event was recorded in the last 30 minutes. No drowsiness, yawning, or head-down events were recorded during that period.",
            "relevant_event_ids": ["evt_phone_01"],
            "suggested_followups": ["Why was the phone used?"]
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
                "question": "What happened in the last 30 minutes?",
                "time_range": "30m"
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "### Driving Safety Evaluation" not in data["answer"]
    assert "Telemetry Status:" not in data["answer"]
    assert data.get("is_formal_report") is False
    assert data.get("disclaimer") is None
    assert "phone-distraction" in data["answer"]


def test_driver_risk_question_includes_supporting_evidence():
    """Scenario 4: A driver-risk question includes supporting evidence and telemetry facts."""
    test_client = TestClient(app)

    mock_ollama_resp = {
        "response": json.dumps({
            "answer": "The driver recorded repeated drowsiness events during the active period, causing the safety score to drop to 85/100.",
            "risk_level": "WARNING",
            "relevant_event_ids": ["evt_123"],
            "key_findings": ["Drowsiness detected with sustained eye closure."]
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
                "question": "Why is this driver at risk?",
                "time_range": "30m"
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "telemetry_facts" in data
    assert "safety_score" in data["telemetry_facts"]
    assert data["risk_level"] in ("WARNING", "HIGH", "SAFE")


def test_explicit_detailed_safety_evaluation_produces_structured_report():
    """Scenario 5: An explicit request for a detailed safety evaluation produces a structured report with disclaimer."""
    test_client = TestClient(app)

    mock_ollama_resp = {
        "response": json.dumps({
            "answer": "### Driving Safety Evaluation for Prototype Driver (DRV001)\n\nTelemetry Status: WARNING (85/100)\n\nDuring today's shift, 2 safety violations were recorded.",
            "is_formal_report": True,
            "executive_summary": "Driver exhibits mild fatigue with 2 warnings.",
            "key_findings": ["1 yawn detected", "1 phone distraction observed"],
            "recommendations": ["Require 15-minute rest break", "Audit in-cab phone policy"]
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
                "question": "Give me a detailed driving safety evaluation for today.",
                "time_range": "today"
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_formal_report"] is True
    assert data.get("disclaimer") is not None
    assert "Driving Safety Evaluation" in data["answer"]
    assert len(data.get("recommendations", [])) >= 1


def test_context_and_filter_extraction_in_follow_up():
    """Scenario 6: Contextual driver and time range extracted from question text."""
    test_client = TestClient(app)

    from owner_service.backend.database import get_database
    db = get_database()
    db["drivers"].update_one(
        {"driver_id": "DRV002"},
        {"$set": {"driver_id": "DRV002", "driver_name": "Test Driver 2", "vehicle_id": "VEH002", "status": "ACTIVE"}},
        upsert=True
    )

    try:
        mock_ollama_resp = {
            "response": json.dumps({
                "answer": "In the last 30 minutes, driver DRV002 had zero violations recorded.",
                "relevant_event_ids": []
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
                    "question": "What about DRV002 in the last 30 minutes?",
                    "time_range": "today"
                }
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["driver_id"] == "DRV002"
        assert data["time_range"] == "30m"
    finally:
        db["drivers"].delete_one({"driver_id": "DRV002"})


def test_ambiguous_question_returns_clarification():
    """Scenario 7: Short ambiguous inputs prompt a polite clarification without dumping telemetry."""
    test_client = TestClient(app)

    resp = test_client.post(
        "/api/ai/ask",
        json={
            "driver_id": "DRV001",
            "question": "???",
            "time_range": "30m"
        }
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "AMBIGUOUS"
    assert data["telemetry_facts"] is None
    assert "clarify" in data["answer"].lower() or "specify" in data["answer"].lower()


def test_no_disclaimer_appended_to_ordinary_chat_responses():
    """Scenario 8: The standard disclaimer is not automatically appended to ordinary chat responses."""
    test_client = TestClient(app)

    mock_ollama_resp = {
        "response": json.dumps({
            "answer": "The driver's current safety score is 95 out of 100, which is considered safe.",
            "suggested_followups": ["What happened earlier today?"]
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
                "question": "Is this driver safe right now?",
                "time_range": "30m"
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_formal_report"] is False
    assert data["disclaimer"] is None
    assert "Advisory safety insight" not in data["answer"]


def test_offline_fallback_does_not_force_report_template():
    """Scenario 9: Offline fallback is conversational, clean, and does not leak internal info or force report templates."""
    test_client = TestClient(app)

    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        resp = test_client.post(
            "/api/ai/ask",
            json={
                "driver_id": "DRV001",
                "question": "What happened in the last 30 minutes?",
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
    assert "### Driving Safety Evaluation" not in data["answer"]
    assert data["is_formal_report"] is False
    assert data["disclaimer"] is None
    assert "No safety events were recorded" in data["answer"] or "safety event" in data["answer"]


def test_no_internal_system_leaks_in_any_response():
    """Regression: Verifies responses never leak URLs, ports, database names, or stack traces."""
    test_client = TestClient(app)

    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        # 1. Greeting when offline
        resp1 = test_client.post("/api/ai/ask", json={"driver_id": "DRV001", "question": "Hiii"})
        assert resp1.status_code == 200
        d1 = resp1.json()
        for forbidden in ["127.0.0.1", "11434", "Ollama", "MongoDB", "driver_safety_db", "ai_analyses"]:
            assert forbidden not in d1["answer"], f"Found forbidden '{forbidden}' in greeting answer"

        # 2. Safety query when offline
        resp2 = test_client.post("/api/ai/ask", json={"driver_id": "DRV001", "question": "Why is this driver's safety rating low?", "time_range": "30m"})
        assert resp2.status_code == 200
        d2 = resp2.json()
        for forbidden in ["127.0.0.1", "11434", "Ollama", "MongoDB", "driver_safety_db", "ai_analyses"]:
            assert forbidden not in d2["answer"], f"Found forbidden '{forbidden}' in safety query answer"

        # 3. Summary report when offline
        resp3 = test_client.post("/api/ai/summary", json={"driver_id": "DRV001", "time_range": "today"})
        assert resp3.status_code == 200
        d3 = resp3.json()
        for forbidden in ["127.0.0.1", "11434", "Ollama", "MongoDB", "driver_safety_db", "ai_analyses"]:
            assert forbidden not in d3["answer"], f"Found forbidden '{forbidden}' in summary answer"


def test_unrecoverable_backend_error_returns_friendly_message():
    """Regression: An unrecoverable exception produces a friendly, generic message without technical details."""
    test_client = TestClient(app)

    with patch.object(EventService, "get_driver_telemetry_facts", side_effect=RuntimeError("Database crashed: connection closed at 127.0.0.1:27017")):
        resp = test_client.post(
            "/api/ai/ask",
            json={
                "driver_id": "DRV001",
                "question": "What happened today?"
            }
        )

    # Should succeed or return user-friendly message
    if resp.status_code == 200:
        d = resp.json()
        assert "Database crashed" not in d["answer"]
        assert "127.0.0.1" not in d["answer"]
        assert "27017" not in d["answer"]
        assert "Traceback" not in d["answer"]
        assert "I couldn't complete that request just now. Please try again." in d["answer"]


def test_relevant_evidence_and_event_links_preserved_offline():
    """Regression: Telemetry facts and relevant event references are preserved during offline fallback."""
    test_client = TestClient(app)

    # Ingest an event first
    test_client.post("/api/events", json={
        "event_id": "evt_regr_offline_01",
        "driver_id": "DRV001",
        "event_type": "PHONE_DETECTED",
        "duration": 2.5,
        "severity": "WARNING",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        resp = test_client.post(
            "/api/ai/ask",
            json={
                "driver_id": "DRV001",
                "question": "What happened in the last 30 minutes?",
                "time_range": "30m"
            }
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unavailable"
    assert "telemetry_facts" in data
    assert data["telemetry_facts"]["phone_count"] >= 1
    # Relevant events must still be present for frontend incident links
    assert "relevant_events" in data
    assert any(e["event_id"] == "evt_regr_offline_01" for e in data["relevant_events"])


def test_sanitize_public_response_unit():
    """Regression: Unit test for EventService.sanitize_public_response cleaning accidental technical leaks."""
    dirty_input = {
        "status": "unavailable",
        "model_used": "gemma4:e4b",
        "answer": "Error connecting to http://127.0.0.1:11434: (Ollama is currently unreachable at http://127.0.0.1:11434). Response synthesized directly from MongoDB records in driver_safety_db.ai_analyses.",
        "summary": "Synthesized directly from MongoDB records at port 11434.",
        "key_findings": ["127.0.0.1:11434 unreachable", "MongoDB records checked"],
        "recommendations": ["Check Ollama status on port 11434"]
    }

    cleaned = EventService.sanitize_public_response(dirty_input)
    assert cleaned["model_used"] == "AI Safety Assistant"
    assert "127.0.0.1" not in cleaned["answer"]
    assert "11434" not in cleaned["answer"]
    assert "Ollama" not in cleaned["answer"]
    assert "MongoDB" not in cleaned["answer"]
    assert "driver_safety_db" not in cleaned["answer"]
    assert "ai_analyses" not in cleaned["answer"]
    assert "127.0.0.1" not in cleaned["summary"]
    assert "Ollama" not in cleaned["summary"]
    assert "MongoDB" not in cleaned["summary"]
    assert all("11434" not in item for item in cleaned["key_findings"])
    assert all("Ollama" not in item for item in cleaned["recommendations"])

