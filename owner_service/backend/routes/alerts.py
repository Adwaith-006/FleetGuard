"""
API endpoints for querying and managing high-risk and critical urgent safety alerts.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, status
from owner_service.backend.database import (
    get_urgent_alerts,
    get_active_alert,
    resolve_urgent_alert
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    driver_id: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200)
):
    """Returns stored urgent alerts sorted by most recent first."""
    return get_urgent_alerts(driver_id=driver_id, limit=limit, status=status_filter)


@router.get("/active")
def get_current_active_alert(driver_id: str = Query(default="DRV001")):
    """Returns the latest active urgent alert for the driver, or None if safe."""
    active = get_active_alert(driver_id=driver_id)
    return {"active": bool(active), "alert": active}


@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: str):
    """Allows fleet owner to acknowledge and dismiss an urgent alert."""
    success = resolve_urgent_alert(alert_id, "RESOLVED")
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Urgent alert '{alert_id}' not found or already resolved."
        )
    return {"status": "success", "alert_id": alert_id, "message": "Alert resolved."}
