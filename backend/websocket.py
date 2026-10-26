import json
import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger("BackendWebSocket")

class ConnectionManager:
    """Manages WebSocket connections and broadcasts real-time safety events to connected clients."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total active clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total active clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcasts a JSON event payload to all active React Admin dashboard clients."""
        if not self.active_connections:
            logger.info("No active WebSocket clients to broadcast event.")
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")
                disconnected.append(connection)

        for dead_conn in disconnected:
            self.disconnect(dead_conn)

manager = ConnectionManager()
