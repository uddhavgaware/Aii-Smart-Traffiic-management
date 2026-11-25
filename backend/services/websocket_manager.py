"""
WebSocket connection manager for live dashboard updates, mobile camera frame relay,
and WebRTC SDP/ICE signaling.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from fastapi import WebSocket

from core.logging import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """Manages active WebSocket clients (dashboards, mobile cameras, ML subscribers)."""

    def __init__(self) -> None:
        self.active_connections: Dict[WebSocket, dict[str, Any]] = {}
        self.camera_sockets: Dict[str, WebSocket] = {}  # direction -> WebSocket
        self.latest_frames: Dict[str, dict[str, Any]] = {}  # direction -> {image, ts, device_id}

    async def connect(
        self,
        websocket: WebSocket,
        username: str = "anonymous",
        role: str = "viewer",
        client_type: str = "dashboard",
    ) -> None:
        await websocket.accept()
        self.active_connections[websocket] = {
            "username": username,
            "role": role,
            "client_type": client_type,
            "connected_at": time.time(),
        }
        logger.info("ws_client_connected", username=username, total=len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> Optional[str]:
        """Remove WebSocket and return direction if it was a registered camera stream."""
        self.active_connections.pop(websocket, None)
        disconnected_dir: Optional[str] = None
        for direction, ws in list(self.camera_sockets.items()):
            if ws is websocket:
                self.camera_sockets.pop(direction, None)
                disconnected_dir = direction
        logger.info("ws_client_disconnected", total=len(self.active_connections), direction=disconnected_dir)
        return disconnected_dir

    def bind_camera(self, direction: str, websocket: WebSocket) -> None:
        self.camera_sockets[direction] = websocket

    def store_camera_frame(self, direction: str, payload: dict[str, Any]) -> None:
        self.latest_frames[direction] = {
            **payload,
            "received_at": time.time(),
        }

    async def send_personal(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)

    async def broadcast(
        self,
        event_type: str,
        payload: dict[str, Any],
        exclude_cameras: bool = False,
        exclude: Optional[WebSocket] = None,
    ) -> None:
        """Broadcast a structured event to connected WebSocket clients."""
        if not self.active_connections:
            return
        cam_sockets = set(self.camera_sockets.values()) if exclude_cameras else set()
        targets = [
            ws
            for ws, meta in list(self.active_connections.items())
            if ws is not exclude
            and not (exclude_cameras and (ws in cam_sockets or meta.get("client_type") == "mobile"))
        ]
        if not targets:
            return
        message = {
            "type": event_type,
            "payload": payload,
            "data": payload,
            "timestamp": time.time(),
        }

        async def _safe_send(ws: WebSocket) -> None:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)

        await asyncio.gather(
            *(_safe_send(ws) for ws in targets),
            return_exceptions=True,
        )

    async def broadcast_raw(self, message: dict[str, Any]) -> None:
        """Broadcast a raw message dict ensuring both payload and data keys exist."""
        event_type = message.get("type", "notification")
        payload = message.get("payload") or message.get("data") or {}
        await self.broadcast(event_type, payload)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


ws_manager = WebSocketManager()
