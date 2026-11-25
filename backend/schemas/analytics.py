"""
Analytics Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AnalyticsQueryRequest(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    direction: Optional[str] = Field(None, pattern="^(north|south|east|west)$")
    interval: str = Field("hour", pattern="^(minute|hour|day)$")


class DirectionStats(BaseModel):
    direction: str
    total_vehicles: int
    avg_density: float
    peak_hour: Optional[str] = None
    avg_queue_length: float
    congestion_events: int


class AnalyticsSummaryResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_vehicles: int
    total_signal_changes: int
    total_emergency_events: int
    avg_wait_time_seconds: float
    peak_direction: Optional[str] = None
    direction_stats: List[DirectionStats]


class TimeSeriesDataPoint(BaseModel):
    timestamp: datetime
    value: float
    direction: Optional[str] = None


class VehicleAnalyticsResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    data_points: List[TimeSeriesDataPoint]
    total: int
    by_direction: Dict[str, int]


class DensityAnalyticsResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    data_points: List[TimeSeriesDataPoint]
    distribution: Dict[str, int]  # low/medium/high/critical counts


class SignalAnalyticsResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_cycles: int
    avg_green_duration: float
    avg_cycle_time: float
    manual_overrides: int
    emergency_overrides: int
    by_direction: Dict[str, Dict[str, float]]


class PerformanceMetrics(BaseModel):
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    gpu_percent: Optional[float] = None
    gpu_memory_mb: Optional[float] = None
    gpu_memory_total_mb: Optional[float] = None
    inference_latency_ms: Optional[float] = None
    websocket_connections: int
    db_pool_size: int
    uptime_seconds: float
