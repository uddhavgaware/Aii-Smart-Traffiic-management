"""
Emergency API routes:
GET  /api/emergency/current
POST /api/emergency/alert
POST /api/emergency/clear
GET  /api/emergency/history
POST /api/emergency/{id}/acknowledge
"""

from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from middleware.auth import get_current_user, require_role, verify_ml_or_user
from models.emergency_event import EmergencyEvent
from models.user import User
from schemas.emergency import (
    EmergencyAlertRequest,
    EmergencyClearRequest,
    EmergencyEventResponse,
)
from services.runtime import runtime

router = APIRouter(prefix="/emergency", tags=["Emergency"])


@router.get("/current")
async def get_current_emergency(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return runtime.emergency_handler.get_current_state()


@router.post("/alert")
async def trigger_emergency_alert(
    payload: EmergencyAlertRequest,
    caller: str = Depends(verify_ml_or_user),
) -> dict[str, Any]:
    result = await runtime.emergency_handler.process_alert(
        direction_str=payload.direction,
        vehicle_type=payload.vehicle_type.value,
        stage=payload.stage,
        confidence=payload.confidence,
        cleared=payload.cleared,
    )
    await runtime.log_system_event(
        "emergency_alert",
        "critical" if payload.stage == 2 else "warning",
        f"{payload.vehicle_type.value.upper()} stage {payload.stage} on {payload.direction.upper()} (conf={payload.confidence:.0%})",
    )
    return result


@router.post("/clear")
async def clear_emergency(
    payload: EmergencyClearRequest = EmergencyClearRequest(),
    current_user: User = Depends(require_role("admin", "operator")),
) -> dict[str, Any]:
    res = await runtime.emergency_handler.clear_emergency(
        reason=payload.reason or f"Cleared by {current_user.username}"
    )
    await runtime.log_system_event(
        "emergency_cleared", "info", f"Emergency cleared by {current_user.username}"
    )
    return res


@router.get("/history", response_model=List[EmergencyEventResponse])
async def get_emergency_history(
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EmergencyEventResponse]:
    stmt = select(EmergencyEvent).order_by(EmergencyEvent.timestamp.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [EmergencyEventResponse.model_validate(r) for r in rows]


@router.post("/{event_id}/acknowledge")
async def acknowledge_emergency(
    event_id: int,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await runtime.log_system_event(
        "emergency_acknowledged", "info", f"Emergency #{event_id} acknowledged by {current_user.username}"
    )
    return {"acknowledged": True, "event_id": event_id}
