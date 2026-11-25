"""
ESP32 HTTP-Polling API endpoints
=================================
GET  /api/hardware/esp32/poll        - ESP32 polls for latest signal command
POST /api/hardware/esp32/ack         - ESP32 acknowledges command execution
POST /api/hardware/esp32/heartbeat   - ESP32 sends periodic heartbeat

No MQTT broker required. ESP32 polls every ~1 second over local WiFi.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from core.logging import get_logger
from services.runtime import runtime
from services.websocket_manager import ws_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/hardware/esp32", tags=["ESP32"])

# ─────────────────────────────────────────────────────────────
# In-memory state for ESP32 connectivity
# ─────────────────────────────────────────────────────────────
_esp32_state: dict[str, Any] = {
    "online": False,
    "last_heartbeat": None,
    "last_ack_seq": None,
    "rssi": None,
    "uptime_ms": None,
    "free_heap": None,
    "phases": {},
    "last_error": None,
}

_last_command_seq: int = 0
_last_command: Optional[dict[str, Any]] = None


def _update_esp32_online() -> None:
    """Mark ESP32 as online and broadcast status to dashboard."""
    was_online = _esp32_state["online"]
    _esp32_state["online"] = True
    _esp32_state["last_heartbeat"] = time.time()
    if not was_online:
        import asyncio
        asyncio.create_task(_broadcast_esp32_status())


async def _broadcast_esp32_status() -> None:
    await ws_manager.broadcast({
        "type": "esp32_status",
        "online": _esp32_state["online"],
        "rssi": _esp32_state["rssi"],
        "phases": _esp32_state["phases"],
        "uptime_ms": _esp32_state["uptime_ms"],
    })


# ─────────────────────────────────────────────────────────────
# Heartbeat staleness checker (call from background task)
# ─────────────────────────────────────────────────────────────
def check_esp32_heartbeat_staleness(timeout_sec: float = 30.0) -> None:
    """Mark ESP32 offline if no heartbeat for timeout_sec."""
    if _esp32_state["online"] and _esp32_state["last_heartbeat"]:
        age = time.time() - _esp32_state["last_heartbeat"]
        if age > timeout_sec:
            _esp32_state["online"] = False
            logger.warning("esp32_heartbeat_timeout", age_sec=age)


# ─────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────
class AckPayload(BaseModel):
    junction_id: str
    sequence_id: int
    ack: bool
    reason: str = ""
    rssi: Optional[int] = None


class HeartbeatPayload(BaseModel):
    junction_id: str
    rssi: Optional[int] = None
    uptime_ms: Optional[int] = None
    free_heap: Optional[int] = None
    phases: dict[str, str] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/poll")
async def esp32_poll(
    junction_id: str = Query(default="junction_001"),
) -> dict[str, Any]:
    """
    ESP32 calls this every ~1s to get the current signal command.
    Returns the latest signal phase from the safety controller.
    """
    global _last_command_seq, _last_command

    _update_esp32_online()

    ctrl = runtime.signal_controller
    state = ctrl.get_current_state()

    # Determine green direction (active_pair may have 1 or 2 directions)
    active_pair = state.get("active_pair", [])
    signals = state.get("signals", {})

    green_dir = None
    duration_ms = 30000

    # Find which direction is currently GREEN
    for dir_name, sig in signals.items():
        if sig.get("phase") == "green":
            green_dir = dir_name
            break

    # Estimate remaining duration from phase_elapsed of the green direction
    if green_dir and green_dir in signals:
        elapsed = signals[green_dir].get("phase_elapsed", 0)
        # Default green window is 30s; remaining = max(5s, 30s - elapsed)
        remaining_ms = max(5000, int((30.0 - elapsed) * 1000))
        duration_ms = remaining_ms

    _last_command_seq += 1
    _last_command = {
        "sequence_id": _last_command_seq,
        "green_direction": green_dir,
        "duration_ms": duration_ms,
        "phase": "green" if green_dir else "all_red",
        "junction_id": junction_id,
        "active_pair": active_pair,
    }

    return _last_command


@router.post("/ack")
async def esp32_ack(payload: AckPayload) -> dict[str, Any]:
    """ESP32 confirms it has applied the signal command."""
    _esp32_state["last_ack_seq"] = payload.sequence_id
    _esp32_state["rssi"] = payload.rssi
    _update_esp32_online()

    if not payload.ack:
        _esp32_state["last_error"] = payload.reason
        logger.warning("esp32_ack_rejected",
                       seq=payload.sequence_id, reason=payload.reason)
    else:
        _esp32_state["last_error"] = None
        logger.info("esp32_ack_ok", seq=payload.sequence_id)

    # Broadcast ACK to dashboard WebSocket
    await ws_manager.broadcast({
        "type": "esp32_ack",
        "sequence_id": payload.sequence_id,
        "ack": payload.ack,
        "reason": payload.reason,
        "rssi": payload.rssi,
    })
    return {"ok": True}


@router.post("/heartbeat")
async def esp32_heartbeat(payload: HeartbeatPayload) -> dict[str, Any]:
    """ESP32 sends periodic status heartbeat."""
    _esp32_state["rssi"]       = payload.rssi
    _esp32_state["uptime_ms"]  = payload.uptime_ms
    _esp32_state["free_heap"]  = payload.free_heap
    _esp32_state["phases"]     = payload.phases
    _update_esp32_online()

    logger.debug("esp32_heartbeat",
                 rssi=payload.rssi, uptime_ms=payload.uptime_ms,
                 phases=payload.phases)

    await _broadcast_esp32_status()
    return {"ok": True, "server_time": time.time()}


@router.get("/status")
async def esp32_status() -> dict[str, Any]:
    """Dashboard reads current ESP32 status."""
    check_esp32_heartbeat_staleness()
    return {
        **_esp32_state,
        "last_heartbeat_age_sec": (
            round(time.time() - _esp32_state["last_heartbeat"], 1)
            if _esp32_state["last_heartbeat"] else None
        ),
    }
