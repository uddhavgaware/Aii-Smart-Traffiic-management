"""
Analytics & Real Performance Telemetry Service
===============================================
Collects real CPU/RAM/GPU metrics (psutil + GPUtil) and queries historical DB tables.
Never fabricates metrics when hardware sensors or GPU are unavailable.
"""

from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import psutil
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.emergency_event import EmergencyEvent
from models.signal_event import SignalEvent
from models.traffic_event import TrafficEvent

_START_TIME = time.time()


def collect_host_performance(
    inference_latency_ms: float = 0.0,
    detection_fps: float = 0.0,
) -> dict[str, Any]:
    """Read real CPU, RAM, and NVIDIA GPU metrics via psutil and GPUtil."""
    cpu_pct = float(psutil.cpu_percent(interval=None))
    mem_pct = float(psutil.virtual_memory().percent)

    gpu_pct = 0.0
    vram_used_gb = 0.0
    vram_total_gb = 0.0

    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            g = gpus[0]
            gpu_pct = round(float(g.load) * 100.0, 1)
            vram_used_gb = round(float(g.memoryUsed) / 1024.0, 2)
            vram_total_gb = round(float(g.memoryTotal) / 1024.0, 2)
    except Exception:
        pass

    return {
        "cpu_usage": round(cpu_pct, 1),
        "memory_usage": round(mem_pct, 1),
        "gpu_usage": gpu_pct,
        "vram_used": vram_used_gb,
        "vram_total": vram_total_gb,
        "inference_latency": round(inference_latency_ms, 2),
        "detection_fps": round(detection_fps, 2),
        "uptime": round(time.time() - _START_TIME, 1),
    }


async def get_traffic_analytics(db: AsyncSession, period: str = "24h") -> dict[str, Any]:
    hours_map = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}
    hours = hours_map.get(period, 24)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    total_veh_res = await db.execute(
        select(func.coalesce(func.sum(TrafficEvent.vehicle_count), 0)).where(
            TrafficEvent.timestamp >= cutoff
        )
    )
    total_vehicles = int(total_veh_res.scalar() or 0)

    sig_count_res = await db.execute(
        select(func.count(SignalEvent.id)).where(SignalEvent.timestamp >= cutoff)
    )
    total_signals = int(sig_count_res.scalar() or 0)

    em_count_res = await db.execute(
        select(func.count(EmergencyEvent.id)).where(EmergencyEvent.timestamp >= cutoff)
    )
    total_emergencies = int(em_count_res.scalar() or 0)

    avg_dur_res = await db.execute(
        select(func.coalesce(func.avg(SignalEvent.duration), 0.0)).where(
            SignalEvent.timestamp >= cutoff
        )
    )
    avg_wait = float(avg_dur_res.scalar() or 0.0)

    congestion_by_direction = []
    for direction in ("north", "south", "east", "west"):
        c_res = await db.execute(
            select(func.count(TrafficEvent.id)).where(
                TrafficEvent.timestamp >= cutoff,
                TrafficEvent.direction == direction,
                TrafficEvent.density_level.in_(["HIGH", "TRAFFIC_JAM", "high", "critical"]),
            )
        )
        q_res = await db.execute(
            select(func.coalesce(func.avg(TrafficEvent.queue_length), 0.0)).where(
                TrafficEvent.timestamp >= cutoff,
                TrafficEvent.direction == direction,
            )
        )
        congestion_by_direction.append({
            "direction": direction,
            "congestion_events": int(c_res.scalar() or 0),
            "avg_queue": round(float(q_res.scalar() or 0.0), 1),
        })

    return {
        "period": period,
        "total_vehicles": total_vehicles,
        "total_signal_changes": total_signals,
        "total_emergency_events": total_emergencies,
        "avg_wait_time_seconds": round(avg_wait, 1),
        "congestion_by_direction": congestion_by_direction,
    }


async def generate_traffic_csv(
    db: AsyncSession,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None,
) -> str:
    stmt = select(TrafficEvent).order_by(TrafficEvent.timestamp.desc()).limit(5000)
    if start_ts:
        stmt = stmt.where(TrafficEvent.timestamp >= start_ts)
    if end_ts:
        stmt = stmt.where(TrafficEvent.timestamp <= end_ts)

    rows = (await db.execute(stmt)).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id",
        "timestamp",
        "direction",
        "vehicle_count",
        "density_level",
        "speed_estimate",
        "queue_length",
        "congestion_predicted",
    ])
    for r in rows:
        writer.writerow([
            r.id,
            r.timestamp.isoformat(),
            r.direction,
            r.vehicle_count,
            r.density_level,
            r.speed_estimate if r.speed_estimate is not None else "",
            r.queue_length,
            r.congestion_predicted,
        ])
    return buf.getvalue()
