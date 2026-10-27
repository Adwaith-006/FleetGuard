"""
API endpoints for driver fleet profiles and live operational status.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from owner_service.backend.services.event_service import EventService
from owner_service.backend.models.payloads import DriverStatusUpdatePayload
from owner_service.backend.websocket import manager

router = APIRouter(prefix="/api/drivers", tags=["drivers"])


@router.get("")
def list_drivers():
    """
    Returns list of fleet drivers with their latest vehicle assignment,
    operational status (ACTIVE/ALERT/OFF_DUTY), and cumulative safety event counts.
    """
    return EventService.get_drivers()


@router.get("/{driver_id}")
def get_driver(driver_id: str):
    """Fetches details for a specific driver by unique driver_id."""
    driver = EventService.get_driver(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver '{driver_id}' not found.")
    return driver


@router.post("/status", status_code=status.HTTP_200_OK)
async def update_status(payload: DriverStatusUpdatePayload):
    """
    Receives live monitoring status telemetry from the Driver Monitoring Service,
    persists current state to MongoDB, and broadcasts update to WebSocket clients.
    """
    data = payload.model_dump()
    driver_id = data.get("driver_id", "DRV001")
    updated = EventService.update_driver(driver_id, data)

    # Broadcast live status update to WebSocket dashboard clients
    await manager.broadcast({
        "type": "DRIVER_STATUS_UPDATE",
        "driver_id": driver_id,
        "status": data.get("status", "ACTIVE"),
        "monitoring_state": data.get("monitoring_state", "Normal"),
        "metrics": data.get("metrics", {}),
        "driver": updated
    })

    # Evaluate temporal telemetry against sustained high-risk and critical rules
    try:
        from owner_service.backend.services.risk_evaluator import RiskEvaluator
        RiskEvaluator.evaluate_telemetry(data)
    except Exception as err:
        pass

    return {"status": "success", "driver": updated}

