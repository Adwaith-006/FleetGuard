import uvicorn
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.config import HOST, PORT, DEMO_DRIVER_ID, DEMO_DRIVER_NAME, DEMO_VEHICLE_ID, DEMO_VEHICLE_NO
    from backend.models import SafetyEventPayload, EventStatusClassifier
    from backend.storage import get_all_events, save_event
    from backend.websocket import manager
except ImportError:
    from config import HOST, PORT, DEMO_DRIVER_ID, DEMO_DRIVER_NAME, DEMO_VEHICLE_ID, DEMO_VEHICLE_NO
    from models import SafetyEventPayload, EventStatusClassifier
    from storage import get_all_events, save_event
    from websocket import manager

app = FastAPI(title="AI Driver Monitoring FastAPI Backend", version="1.0.0")

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/events")
def fetch_events():
    """Returns all stored events from data/events.json."""
    return get_all_events()

@app.post("/api/events")
async def receive_event(payload: SafetyEventPayload):
    """
    Receives a completed safety event from the Python AI system,
    applies objective status classification, stores it, and broadcasts
    it to all connected React Admin WebSocket clients.
    """
    event_dict = payload.model_dump()
    
    # Apply objective duration-based status classification
    objective_status = EventStatusClassifier.classify_status(
        event_dict.get("event_type"),
        event_dict.get("duration", 0.0)
    )
    event_dict["status"] = objective_status

    # Set demo metadata if omitted
    if not event_dict.get("driver_id"):
        event_dict["driver_id"] = DEMO_DRIVER_ID
        event_dict["driver_name"] = DEMO_DRIVER_NAME
    if not event_dict.get("vehicle_id"):
        event_dict["vehicle_id"] = DEMO_VEHICLE_ID
        event_dict["vehicle_no"] = DEMO_VEHICLE_NO

    if not event_dict.get("session_id"):
        event_dict["session_id"] = "sess_live"

    if not event_dict.get("timestamp"):
        event_dict["timestamp"] = datetime.now().isoformat()

    # Save to local storage
    saved = save_event(event_dict)

    # Broadcast real-time event to React Admin Dashboard via WebSocket
    await manager.broadcast({
        "type": "NEW_SAFETY_EVENT",
        "event": saved
    })

    return {"status": "success", "event": saved}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "message": "Connected to AI Driver Safety Backend WebSocket"
        })
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
