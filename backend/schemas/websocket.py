"""
WebSocket message Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    # Outbound (server → client)
    SIGNAL_UPDATE = "signal_update"
    TRAFFIC_UPDATE = "traffic_update"
    CAMERA_UPDATE = "camera_update"
    EMERGENCY_ALERT = "emergency_alert"
    SYSTEM_STATUS = "system_status"
    PERFORMANCE_UPDATE = "performance_update"
    NOTIFICATION = "notification"
    # Inbound (client → server)
    PING = "ping"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    # Internal
    PONG = "pong"
    ERROR = "error"
    CONNECTED = "connected"


class WebSocketMessage(BaseModel):
    type: EventType
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "server"


class WebSocketSubscribeRequest(BaseModel):
    type: EventType = EventType.SUBSCRIBE
    channels: list[str] = Field(default_factory=list)


class NotificationMessage(BaseModel):
    severity: str = "info"  # info | warning | error | critical
    title: str
    message: str
    event_type: Optional[str] = None
