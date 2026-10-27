"""
Health check endpoints for Owner Management Service.
Reports backend health, MongoDB connection status, and Ollama/Gemma availability.
"""

from datetime import datetime, timezone
from fastapi import APIRouter
from owner_service.backend.database import check_health as check_mongo_health
from owner_service.ai.gemma_service import GemmaService

router = APIRouter(prefix="/api/health", tags=["health"])
gemma_service = GemmaService()


@router.get("")
def health_check():
    """
    Returns unified operational status for:
    - FastAPI Backend service
    - MongoDB Database connection and server version
    - Local Ollama AI service and active Gemma model
    """
    mongo_health = check_mongo_health()
    ai_health = gemma_service.check_health()

    is_overall_healthy = (mongo_health.get("status") == "connected")

    return {
        "status": "healthy" if is_overall_healthy else "degraded",
        "service": "owner_management_service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": mongo_health.get("status", "disconnected")
        },
        "ai": {
            "status": "available" if ai_health.get("available") else "standby"
        }
    }
