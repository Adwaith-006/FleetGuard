"""
WebSocket connection manager for real-time fleet owner alerts.
Broadcasts newly ingested safety events and Gemma explanations to connected React dashboards.
"""

import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger("OwnerWebSocket")


class ConnectionManager:
    """Manages active WebSocket client connections for the Owner Dashboard."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Dashboard client connected. Active dashboard clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Dashboard client disconnected. Active dashboard clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcasts a JSON event payload to all active React Admin dashboard clients."""
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to transmit WebSocket message: {e}")
                disconnected.append(connection)

        for dead_conn in disconnected:
            self.disconnect(dead_conn)


manager = ConnectionManager()
