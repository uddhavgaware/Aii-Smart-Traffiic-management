"""
Traffic data API routes:
GET  /api/traffic/current
GET  /api/traffic/history
GET  /api/traffic/analytics
GET  /api/traffic/export
GET  /api/traffic/{direction}
POST /api/traffic/update
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import db_session, get_db
from core.redis_client import cache_set_traffic_state
from middleware.auth import get_current_user, verify_ml_or_user
from models.traffic_event import TrafficEvent
from models.user import User
from schemas.traffic import TrafficDataRequest, TrafficDataResponse
from services.analytics_service import generate_traffic_csv, get_traffic_analytics
from services.runtime import runtime
from services.signal_controller import Direction
from services.traffic_intelligence import DirectionTrafficData
from services.websocket_manager import ws_manager

router = APIRouter(prefix="/traffic", tags=["Traffic"])
_LAST_DB_PERSIST: dict[str, float] = {}


_DENSITY_LEVEL_FLOOR = {
    "LOW": 10.0,
    "NORMAL": 30.0,
    "MEDIUM": 55.0,
    "HIGH": 75.0,
    "TRAFFIC_JAM": 92.0,
}


@router.get("/current")
async def get_current_traffic(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return latest real-time traffic metrics for all four approaches."""
    data = runtime.traffic_engine.get_all_traffic_data()
    for d in ("north", "south", "east", "west"):
        info = data[d]
        level = str(info.get("density_level", "LOW"))
        floor_pct = _DENSITY_LEVEL_FLOOR.get(level, 10.0)
        count_pct = min(100.0, round(info.get("vehicle_count", 0) * 2.5, 1))
        queue_pct = float(info.get("queue_length", 0.0) or 0.0)
        info["density"] = round(min(100.0, max(floor_pct, count_pct, queue_pct)), 1)
    return data


@router.get("/history", response_model=List[TrafficDataResponse])
async def get_traffic_history(
    direction: Optional[str] = Query(default=None, pattern="^(north|south|east|west)$"),
    hours: int = Query(default=24, ge=1, le=720),
    limit: int = Query(default=200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[TrafficDataResponse]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = select(TrafficEvent).where(TrafficEvent.timestamp >= cutoff)
    if direction:
        stmt = stmt.where(TrafficEvent.direction == direction)
    stmt = stmt.order_by(TrafficEvent.timestamp.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [TrafficDataResponse.model_validate(r) for r in reversed(rows)]


@router.get("/analytics")
async def traffic_analytics(
    period: str = Query(default="24h", pattern="^(1h|6h|24h|7d)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await get_traffic_analytics(db, period=period)


@router.get("/export")
async def export_traffic_csv(
    from_ts: Optional[int] = Query(default=None, alias="from"),
    to_ts: Optional[int] = Query(default=None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    start_dt = datetime.fromtimestamp(from_ts, tz=timezone.utc) if from_ts else None
    end_dt = datetime.fromtimestamp(to_ts, tz=timezone.utc) if to_ts else None
    csv_body = await generate_traffic_csv(db, start_dt, end_dt)
    return Response(
        content=csv_body,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=smarttraffic-export.csv"},
    )


@router.get("/{direction}")
async def get_direction_traffic(
    direction: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    all_data = runtime.traffic_engine.get_all_traffic_data()
    if direction not in all_data:
        return {"error": "Invalid direction"}
    return all_data[direction]


async def ingest_traffic_payload(
    payload: TrafficDataRequest,
    db: Optional[AsyncSession] = None,
) -> None:
    """Ingest ML inference output, persist periodically, and broadcast to dashboards."""
    runtime.ai_engine_status = "running"
    direction = Direction(payload.direction)

    data = DirectionTrafficData(
        direction=direction,
        vehicle_count=payload.vehicle_count,
        density_level=payload.density_level.value,
        speed_estimate=payload.speed_estimate,
        speed_is_estimate=payload.speed_is_estimate,
        queue_length=payload.queue_length,
        congestion_predicted=payload.congestion_predicted,
        predicted_count=payload.predicted_count,
        emergency_detected=payload.emergency_detected,
        emergency_type=payload.emergency_type,
        emergency_stage2_confirmed=payload.emergency_stage2_confirmed,
        emergency_confidence=payload.emergency_confidence,
    )
    runtime.traffic_engine.update_direction_data(data)

    # Persist historical TrafficEvent at most once every 5s per direction to avoid SQLite write contention
    now = time.time()
    if (now - _LAST_DB_PERSIST.get(payload.direction, 0.0)) >= 5.0:
        _LAST_DB_PERSIST[payload.direction] = now
        row = TrafficEvent(
            direction=payload.direction,
            vehicle_count=payload.vehicle_count,
            density_level=payload.density_level.value,
            speed_estimate=payload.speed_estimate,
            queue_length=payload.queue_length,
            congestion_predicted=payload.congestion_predicted,
        )
        if db is not None:
            db.add(row)
        else:
            try:
                async with db_session() as session:
                    session.add(row)
            except Exception:
                pass

    if payload.emergency_detected and payload.emergency_type in ("ambulance", "fire_brigade"):
        await runtime.emergency_handler.process_alert(
            direction_str=payload.direction,
            vehicle_type=payload.emergency_type,
            stage=2 if payload.emergency_stage2_confirmed else 1,
            confidence=payload.emergency_confidence,
        )

    await cache_set_traffic_state(
        payload.direction,
        {
            "vehicle_count": payload.vehicle_count,
            "density_level": payload.density_level.value,
            "density": payload.density_score,
            "speed_estimate": payload.speed_estimate,
            "queue_length": payload.queue_length,
        },
    )

    await ws_manager.broadcast(
        "traffic_update",
        {
            "direction": payload.direction,
            "count": payload.vehicle_count,
            "vehicle_count": payload.vehicle_count,
            "speed": payload.speed_estimate or 0,
            "speed_is_estimate": payload.speed_is_estimate,
            "queue_length": payload.queue_length,
            "density": payload.density_score,
            "density_level": payload.density_level.value,
            "predicted_count": payload.predicted_count,
            "congestion_predicted": payload.congestion_predicted,
            "trend": "increasing" if payload.congestion_predicted else "stable",
        },
        exclude_cameras=True,
    )
    await ws_manager.broadcast(
        "camera_update",
        {
            "direction": payload.direction,
            "vehicle_count": payload.vehicle_count,
            "density": payload.density_score,
            "fps": payload.fps,
            "status": "connected",
            "detections": payload.detections,
            "snapshot": payload.snapshot,
        },
        exclude_cameras=True,
    )


@router.post("/update")
async def update_traffic_from_ml(
    payload: TrafficDataRequest,
    db: AsyncSession = Depends(get_db),
    caller: str = Depends(verify_ml_or_user),
) -> dict[str, Any]:
    """Receive detection, density, speed, queue, and emergency status from ML inference service."""
    await ingest_traffic_payload(payload, db=db)
    return {"status": "accepted", "direction": payload.direction, "caller": caller}
