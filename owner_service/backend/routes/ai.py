"""
API endpoints for local Gemma AI analysis via Ollama.
Provides structured event analysis and retrieves historical AI insights.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, status
from owner_service.backend.models.payloads import (
    AnalyzeRequest,
    AskSafetyQuestionPayload,
    SafetySummaryRequestPayload
)
from owner_service.backend.services.event_service import EventService, gemma_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/ask", status_code=status.HTTP_200_OK)
def ask_driver_safety(payload: AskSafetyQuestionPayload):
    """
    Asks the local Gemma model a natural language question about a specific driver.
    Anchors prompt strictly to verified telemetry facts from MongoDB.
    Saves analysis to MongoDB and returns validated structured response.
    """
    result = EventService.ask_driver_question(
        driver_id=payload.driver_id,
        question=payload.question,
        time_range=payload.time_range or "30m",
        conversation_history=payload.conversation_history
    )
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result.get("message", f"Driver '{payload.driver_id}' not found."))
    return result


@router.post("/summary", status_code=status.HTTP_200_OK)
def generate_driver_summary(payload: SafetySummaryRequestPayload):
    """
    Generates a structured periodic safety evaluation and risk report for a driver.
    Saves the report to MongoDB and returns structured summary and recommendations.
    """
    result = EventService.generate_driver_summary(
        driver_id=payload.driver_id,
        time_range=payload.time_range or "today"
    )
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result.get("message", f"Driver '{payload.driver_id}' not found."))
    return result


@router.post("/analyze", status_code=status.HTTP_200_OK)
def analyze_event(request: AnalyzeRequest):
    """
    Submits an existing safety event to local Gemma via Ollama.
    Produces a structured summary, risk level, supporting evidence,
    and practical recommendations, and saves the result to MongoDB.
    """
    result = EventService.analyze_event_now(event_id=request.event_id, model=request.model)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result.get("message", f"Event '{request.event_id}' not found."))
    return result


@router.get("/analyses")
def list_analyses(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    event_id: Optional[str] = Query(default=None),
    driver_id: Optional[str] = Query(default=None),
    analysis_type: Optional[str] = Query(default=None)
):
    """
    Retrieves historical Gemma AI safety analyses stored in MongoDB.
    Supports filtering by driver_id, event_id, and analysis_type.
    """
    return EventService.list_analyses(
        limit=limit,
        skip=skip,
        event_id=event_id,
        driver_id=driver_id,
        analysis_type=analysis_type
    )


@router.get("/status")
def ai_status():
    """Checks the health, connection, and installed models of the local Ollama service."""
    return gemma_service.check_health()

