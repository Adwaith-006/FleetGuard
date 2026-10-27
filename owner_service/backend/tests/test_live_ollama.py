"""
Live verification test against locally installed Gemma on Ollama.
Only runs if Ollama daemon is reachable on 127.0.0.1:11434.
"""

import pytest
from owner_service.ai.gemma_service import GemmaService
from owner_service.backend.services.event_service import EventService
from owner_service.backend.database import get_all_analyses, init_db


def test_live_ollama_and_gemma_model():
    service = GemmaService()
    health = service.check_health()
    if not health.get("ollama_running"):
        pytest.skip("Ollama daemon is not running on 127.0.0.1:11434.")

    assert health["ollama_running"] is True
    assert health["gemma_installed"] is True
    print(f"\nInstalled models on Ollama: {health.get('installed_models')}")
    print(f"Target model: {health.get('target_model')}")

    # Test live driver safety Q&A
    init_db()
    res = EventService.ask_driver_question(
        driver_id="DRV001",
        question="What are the main safety recommendations for this driver?",
        time_range="30m"
    )

    print("\n--- Live Gemma Response ---")
    print("Status:", res.get("status"))
    print("Model:", res.get("model_used"))
    print("Risk Level:", res.get("risk_level"))
    print("Executive Summary:", res.get("executive_summary"))
    print("Recommendations:", res.get("recommendations"))
    print("Analysis ID:", res.get("analysis_id"))

    assert res.get("status") in ("success", "completed")
    assert res.get("analysis_id") is not None
    assert "telemetry_facts" in res

    # Verify MongoDB persistence
    stored = get_all_analyses(limit=5, driver_id="DRV001")
    assert any(a.get("analysis_id") == res.get("analysis_id") for a in stored)
