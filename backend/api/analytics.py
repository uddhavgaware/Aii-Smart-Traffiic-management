"""
Analytics API routes:
GET /api/analytics/summary
GET /api/analytics/vehicles
GET /api/analytics/density
GET /api/analytics/signals
GET /api/analytics/performance
GET /api/analytics/export/csv
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from middleware.auth import get_current_user
from models.signal_event import SignalEvent
from models.traffic_event import TrafficEvent
from models.user import User
from services.analytics_service import (
    collect_host_performance,
    generate_traffic_csv,
    get_traffic_analytics,
)
from services.runtime import runtime

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
async def analytics_summary(
    period: str = Query(default="24h", pattern="^(1h|6h|24h|7d)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await get_traffic_analytics(db, period=period)


@router.get("/vehicles")
async def analytics_vehicles(
    hours: int = Query(default=24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    by_dir: dict[str, int] = {}
    for d in ("north", "south", "east", "west"):
        res = await db.execute(
            select(func.coalesce(func.sum(TrafficEvent.vehicle_count), 0)).where(
                TrafficEvent.timestamp >= cutoff,
                TrafficEvent.direction == d,
            )
        )
        by_dir[d] = int(res.scalar() or 0)
    return {"total": sum(by_dir.values()), "by_direction": by_dir}


@router.get("/density")
async def analytics_density(
    hours: int = Query(default=24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        await db.execute(
            select(TrafficEvent.density_level, func.count(TrafficEvent.id))
            .where(TrafficEvent.timestamp >= cutoff)
            .group_by(TrafficEvent.density_level)
        )
    ).all()
    return {"distribution": {str(level): int(cnt) for level, cnt in rows}}


@router.get("/signals")
async def analytics_signals(
    hours: int = Query(default=24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    total = (
        await db.execute(select(func.count(SignalEvent.id)).where(SignalEvent.timestamp >= cutoff))
    ).scalar() or 0
    avg_dur = (
        await db.execute(select(func.coalesce(func.avg(SignalEvent.duration), 0.0)).where(SignalEvent.timestamp >= cutoff))
    ).scalar() or 0.0
    manual = (
        await db.execute(
            select(func.count(SignalEvent.id)).where(
                SignalEvent.timestamp >= cutoff, SignalEvent.mode == "MANUAL"
            )
        )
    ).scalar() or 0
    return {
        "total_events": int(total),
        "avg_duration_seconds": round(float(avg_dur), 1),
        "manual_overrides": int(manual),
    }


@router.get("/performance")
async def analytics_performance(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return collect_host_performance(
        inference_latency_ms=runtime.last_inference_latency_ms,
        detection_fps=runtime.last_detection_fps,
    )


@router.get("/export/csv")
async def export_csv(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    csv_body = await generate_traffic_csv(db, start_time, end_time)
    return Response(
        content=csv_body,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=smarttraffic-analytics.csv"},
    )
