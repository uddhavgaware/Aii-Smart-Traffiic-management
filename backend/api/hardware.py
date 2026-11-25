"""
ESP32 Hardware Control API routes:
GET  /api/hardware/status
POST /api/hardware/reboot
POST /api/hardware/test
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from middleware.auth import get_current_user, require_role
from models.user import User
from services.mqtt_service import mqtt_service
from services.runtime import runtime

router = APIRouter(prefix="/hardware", tags=["Hardware"])


class HardwareTestRequest(BaseModel):
    direction: str = Field(..., pattern="^(north|south|east|west)$")


@router.get("/status")
async def get_hardware_status(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return mqtt_service.get_status()


@router.post("/reboot")
async def reboot_esp32(current_user: User = Depends(require_role("admin"))) -> dict[str, Any]:
    ok = await mqtt_service.publish_raw_command("system/command", {"cmd": "reboot"})
    if not ok:
        raise HTTPException(status_code=503, detail="MQTT broker unavailable — cannot send reboot command to ESP32")
    await runtime.log_system_event("esp32_reboot", "warning", f"ESP32 reboot issued by {current_user.username}")
    return {"sent": True}


@router.post("/test")
async def test_direction_leds(
    payload: HardwareTestRequest,
    current_user: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    ok = await mqtt_service.publish_raw_command(
        "system/command", {"cmd": "test_leds", "direction": payload.direction}
    )
    if not ok:
        raise HTTPException(status_code=503, detail="MQTT broker unavailable — ESP32 offline")
    return {"sent": True, "direction": payload.direction}
