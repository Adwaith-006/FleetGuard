"""
API endpoints for driver safety event ingestion and querying.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, status
from owner_service.backend.models.payloads import SafetyEventPayload
from owner_service.backend.services.event_service import EventService
from owner_service.backend.websocket import manager

import logging

logger = logging.getLogger("EventsRouter")
router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    driver_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None)
):
    """
    Returns stored safety events with pagination and optional filtering
    by driver_id, severity (SAFE/WARNING/CRITICAL), and event_type.
    """
    return EventService.list_events(
        limit=limit,
        skip=skip,
        driver_id=driver_id,
        severity=severity,
        event_type=event_type
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def receive_event(payload: SafetyEventPayload):
    """
    Ingests a safety event from the Driver Monitoring Service,
    validates it, persists it to MongoDB, and broadcasts it to connected dashboards.
    """
    event_dict = payload.model_dump()
    try:
        saved = EventService.process_incoming_event(event_dict)
    except Exception as e:
        logger.error(f"Failed to persist safety event: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database persistence failed: {str(e)}"
        )

    # Broadcast event to active dashboard clients over WebSocket
    await manager.broadcast({
        "type": "NEW_SAFETY_EVENT",
        "event": saved
    })

    # Evaluate event against critical risk rules
    try:
        from owner_service.backend.services.risk_evaluator import RiskEvaluator
        RiskEvaluator.evaluate_event(saved)
    except Exception as err:
        pass

    return {"status": "success", "event": saved}


@router.get("/{event_id}")
def get_event(event_id: str):
    """Fetches details for a specific safety event by its unique ID."""
    event = EventService.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")
    return event
