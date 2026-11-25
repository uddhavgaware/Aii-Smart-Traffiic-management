"""
Signal control API routes:
GET   /api/signals/state
POST  /api/signals/mode
POST  /api/signals/override  (alias: /api/signals/command)
GET   /api/signals/config
PUT   /api/signals/config    (alias: PATCH /api/signals/timing)
GET   /api/signals/history
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from middleware.auth import get_current_user, require_role
from models.signal_event import SignalEvent
from models.user import User
from schemas.signal import (
    SignalCommandRequest,
    SignalConfigRequest,
    SignalConfigResponse,
    SignalHistoryItem,
    SignalModeRequest,
    SignalPhase,
)
from services.runtime import runtime
from services.signal_controller import Direction

router = APIRouter(prefix="/signals", tags=["Signals"])


class SignalTimingPatchRequest(BaseModel):
    min_green: int = Field(15, ge=5, le=60)
    max_green: int = Field(120, ge=30, le=300)
    yellow_duration: int = Field(3, ge=2, le=10)
    all_red_duration: int = Field(2, ge=1, le=10)
    max_wait: int = Field(180, ge=60, le=600)


@router.get("/state")
async def get_signal_state(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        **runtime.get_signal_state_payload(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/mode")
async def set_signal_mode(
    payload: SignalModeRequest,
    current_user: User = Depends(require_role("admin", "operator")),
) -> dict[str, Any]:
    if payload.mode.value == "AUTO":
        runtime.signal_controller.resume_auto()
    else:
        from services.signal_controller import SignalMode
        runtime.signal_controller.current_mode = SignalMode.MANUAL

    await runtime.log_system_event(
        "signal_mode_changed",
        "info",
        f"Mode changed to {payload.mode.value} by {current_user.username}",
    )
    await runtime.on_signal_broadcast({})
    return {"mode": runtime.signal_controller.current_mode.value}


@router.post("/override")
@router.post("/command")
async def override_signal(
    payload: SignalCommandRequest,
    current_user: User = Depends(require_role("admin", "operator")),
) -> dict[str, Any]:
    """Execute safe manual override (GREEN for direction's compatible pair or ALL RED)."""
    if runtime.signal_controller.emergency_active:
        raise HTTPException(
            status_code=409,
            detail="Cannot manually override while emergency priority is active",
        )

    direction = Direction(payload.direction)
    if payload.phase == SignalPhase.RED:
        await runtime.signal_controller._apply_all_red(f"manual_all_red_{current_user.username}")
        await runtime.log_system_event(
            "manual_override", "warning", f"ALL-RED triggered by {current_user.username}"
        )
        return {"status": "all_red_applied"}

    pair = runtime.signal_controller._get_pair_for_direction(direction)
    await runtime.signal_controller.manual_command(pair, float(payload.duration), current_user.username)
    await runtime.log_system_event(
        "manual_override",
        "warning",
        f"Manual GREEN override for {[d.value for d in pair]} ({payload.duration}s) by {current_user.username}",
    )
    return {"status": "override_applied", "pair": [d.value for d in pair], "duration": payload.duration}


@router.get("/config", response_model=SignalConfigResponse)
async def get_signal_config(
    current_user: User = Depends(get_current_user),
) -> SignalConfigResponse:
    sc = runtime.signal_controller
    return SignalConfigResponse(
        min_green_time=int(sc.MIN_GREEN_TIME),
        max_green_time=int(sc.MAX_GREEN_TIME),
        yellow_time=int(sc.YELLOW_TIME),
        all_red_time=int(sc.ALL_RED_TIME),
        max_wait_time=int(sc.MAX_WAIT_TIME),
        updated_at=datetime.now(timezone.utc),
    )


@router.put("/config", response_model=SignalConfigResponse)
async def update_signal_config(
    payload: SignalConfigRequest,
    current_user: User = Depends(require_role("admin")),
) -> SignalConfigResponse:
    if payload.min_green_time >= payload.max_green_time:
        raise HTTPException(status_code=400, detail="min_green_time must be < max_green_time")
    sc = runtime.signal_controller
    sc.MIN_GREEN_TIME = float(payload.min_green_time)
    sc.MAX_GREEN_TIME = float(payload.max_green_time)
    sc.YELLOW_TIME = float(payload.yellow_time)
    sc.ALL_RED_TIME = float(payload.all_red_time)
    sc.MAX_WAIT_TIME = float(payload.max_wait_time)
    await runtime.log_system_event("signal_config_updated", "info", f"Timing updated by {current_user.username}")
    return await get_signal_config(current_user)


@router.patch("/timing")
async def patch_signal_timing(
    payload: SignalTimingPatchRequest,
    current_user: User = Depends(require_role("admin", "operator")),
) -> SignalConfigResponse:
    req = SignalConfigRequest(
        min_green_time=payload.min_green,
        max_green_time=payload.max_green,
        yellow_time=payload.yellow_duration,
        all_red_time=payload.all_red_duration,
        max_wait_time=payload.max_wait,
    )
    sc = runtime.signal_controller
    sc.MIN_GREEN_TIME = float(req.min_green_time)
    sc.MAX_GREEN_TIME = float(req.max_green_time)
    sc.YELLOW_TIME = float(req.yellow_time)
    sc.ALL_RED_TIME = float(req.all_red_time)
    sc.MAX_WAIT_TIME = float(req.max_wait_time)
    await runtime.log_system_event("signal_config_updated", "info", f"Timing updated by {current_user.username}")
    return await get_signal_config(current_user)


@router.get("/history", response_model=List[SignalHistoryItem])
async def get_signal_history(
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[SignalHistoryItem]:
    stmt = select(SignalEvent).order_by(SignalEvent.timestamp.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [SignalHistoryItem.model_validate(r) for r in rows]
