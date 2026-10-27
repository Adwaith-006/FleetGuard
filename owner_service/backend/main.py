"""
Owner Management Service - FastAPI Backend Entry Point.
Provides REST APIs and WebSockets for fleet event review and Gemma AI assistance.
Powered by FastAPI + MongoDB (PyMongo) + local Gemma via Ollama.
"""

import sys
import os
from pathlib import Path

# Ensure proper Python path resolution
BACKEND_DIR = Path(__file__).resolve().parent
SERVICE_DIR = BACKEND_DIR.parent
REPO_ROOT = SERVICE_DIR.parent
for p in (str(REPO_ROOT), str(SERVICE_DIR), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from owner_service.backend.database import init_db
from owner_service.backend.websocket import manager
from owner_service.backend.routes import (
    events_router,
    health_router,
    drivers_router,
    ai_router,
    alerts_router
)

app = FastAPI(
    title="AI Fleet Owner Safety & Management Service",
    description="Backend API and live event streaming for commercial fleet management with MongoDB and Gemma AI",
    version="2.0.0"
)

# Enable CORS for React frontend (Vite port 5173 / localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(events_router)
app.include_router(health_router)
app.include_router(drivers_router)
app.include_router(ai_router)
app.include_router(alerts_router)


@app.on_event("startup")
def on_startup():
    """Initializes local MongoDB collections and indexes on server boot."""
    init_db()


async def handle_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "message": "Connected to Fleet Safety Real-Time Stream"
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


@app.websocket("/ws")
async def websocket_ws(websocket: WebSocket):
    """Real-time event streaming endpoint (standard /ws)."""
    await handle_ws(websocket)


@app.websocket("/ws/events")
async def websocket_ws_events(websocket: WebSocket):
    """Real-time event streaming endpoint (/ws/events)."""
    await handle_ws(websocket)


if __name__ == "__main__":
    uvicorn.run("owner_service.backend.main:app", host="0.0.0.0", port=8000, reload=True)
