"""
System monitoring, health, configuration, events, and Demo Mode API routes.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.redis_client import health_check as redis_health_check
from middleware.auth import get_current_user, require_role
from models.system_event import SystemEvent
from models.user import User
from services.analytics_service import collect_host_performance
from services.mqtt_service import mqtt_service
from services.runtime import runtime
from services.websocket_manager import ws_manager

router = APIRouter(prefix="/system", tags=["System"])
_LAST_ML_PROBE_AT: float = 0.0


async def _refresh_ai_status(force: bool = False) -> bool:
    """Probe ML_INFERENCE_URL with short timeout and 8s cache so /status never lags."""
    global _LAST_ML_PROBE_AT
    now = time.time()
    if not force and (now - _LAST_ML_PROBE_AT) < 8.0:
        return runtime.ai_engine_status == "running"

    _LAST_ML_PROBE_AT = now
    ml_url = (settings.ML_INFERENCE_URL or "").strip().rstrip("/")
    ml_ok = False
    if ml_url:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                r = await client.get(f"{ml_url}/infer/status")
                ml_ok = r.status_code == 200
        except Exception:
            ml_ok = False
    runtime.ai_engine_status = "running" if (ml_ok or runtime.demo_mode) else "stopped"
    return ml_ok


class DemoToggleRequest(BaseModel):
    enabled: bool


@router.get("/health")
async def system_health(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    redis_ok = await redis_health_check()
    ml_ok = await _refresh_ai_status(force=True)

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": db_ok,
        "redis": redis_ok,
        "mqtt": mqtt_service.connected,
        "esp32": mqtt_service.esp32_online,
        "ml_service": ml_ok,
        "demo_mode": runtime.demo_mode,
        "uptime": round(time.time() - runtime.start_time, 1),
    }


@router.get("/status")
async def get_system_status(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _refresh_ai_status(force=False)
    return {
        "junction_status": "online",
        "ai_engine_status": runtime.ai_engine_status,
        "esp32_connected": mqtt_service.esp32_online,
        "mqtt_connected": mqtt_service.connected,
        "demo_mode": runtime.demo_mode,
        "uptime": round(time.time() - runtime.start_time, 1),
        "version": settings.APP_VERSION,
    }


@router.get("/metrics")
@router.get("/performance")
async def get_performance_metrics(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return collect_host_performance(
        inference_latency_ms=runtime.last_inference_latency_ms,
        detection_fps=runtime.last_detection_fps,
    )


@router.get("/settings")
async def get_settings(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return runtime.settings_store


@router.patch("/settings")
async def update_settings(
    payload: dict[str, Any],
    current_user: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    allowed_keys = {"resolution", "fps_per_camera", "density_thresholds"}
    for key in allowed_keys:
        if key in payload:
            runtime.settings_store[key] = payload[key]
    await runtime.log_system_event("settings_updated", "info", f"Settings updated by {current_user.username}")
    return runtime.settings_store


@router.post("/ai/restart")
async def check_or_restart_ai(
    current_user: User = Depends(require_role("admin", "operator")),
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.ML_INFERENCE_URL}/infer/status")
            if r.status_code == 200:
                runtime.ai_engine_status = "running"
                return {"status": "ml_service_online", "details": r.json()}
    except Exception as exc:
        runtime.ai_engine_status = "stopped"
        raise HTTPException(status_code=503, detail=f"ML inference service unreachable: {exc}")
    return {"status": "checked"}


@router.post("/demo/toggle")
async def toggle_demo_mode(
    payload: DemoToggleRequest,
    current_user: User = Depends(require_role("admin", "operator")),
) -> dict[str, Any]:
    runtime.demo_mode = payload.enabled
    runtime.ai_engine_status = "running" if payload.enabled else "stopped"
    await ws_manager.broadcast(
        "system_status",
        {
            "junction_status": "online",
            "ai_engine_status": runtime.ai_engine_status,
            "mqtt_connected": mqtt_service.connected,
            "esp32_connected": mqtt_service.esp32_online,
            "demo_mode": runtime.demo_mode,
            "uptime": round(time.time() - runtime.start_time, 1),
        },
    )
    await runtime.log_system_event(
        "demo_mode_toggled",
        "warning" if payload.enabled else "info",
        f"Demo mode {'ENABLED' if payload.enabled else 'DISABLED'} by {current_user.username}",
    )
    return {"demo_mode": runtime.demo_mode}


@router.get("/events")
async def get_system_events(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[dict[str, Any]]:
    stmt = select(SystemEvent).order_by(SystemEvent.timestamp.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "event_type": r.event_type,
            "severity": r.severity,
            "message": r.message,
            "acknowledged": r.acknowledged,
        }
        for r in rows
    ]


@router.post("/events/{event_id}/acknowledge")
async def acknowledge_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await db.execute(
        update(SystemEvent)
        .where(SystemEvent.id == event_id)
        .values(
            acknowledged=True,
            acknowledged_at=datetime.now(timezone.utc),
            acknowledged_by=current_user.username,
        )
    )
    return {"acknowledged": True, "id": event_id}


@router.get("/esp32/status")
async def get_esp32_status(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return mqtt_service.get_status()
