"""
Traffic Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class DensityLevel(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    TRAFFIC_JAM = "TRAFFIC_JAM"


class TrafficDataRequest(BaseModel):
    """Payload sent by the ML inference service."""
    direction: str = Field(..., pattern="^(north|south|east|west)$")
    vehicle_count: int = Field(..., ge=0)
    density_level: DensityLevel
    density_score: float = Field(0.0, ge=0.0, le=100.0)
    speed_estimate: Optional[float] = Field(None, ge=0)
    speed_is_estimate: bool = True
    queue_length: float = Field(0.0, ge=0)
    congestion_predicted: bool = False
    predicted_count: Optional[int] = None
    fps: float = 0.0
    detections: List[dict[str, Any]] = Field(default_factory=list)
    snapshot: Optional[str] = None
    emergency_detected: bool = False
    emergency_type: Optional[str] = None
    emergency_stage2_confirmed: bool = False
    emergency_confidence: float = 0.0
    timestamp: Optional[datetime] = None

    @field_validator("density_level", mode="before")
    @classmethod
    def normalize_density(cls, v: Any) -> str:
        if isinstance(v, str):
            norm = v.strip().upper().replace(" ", "_")
            if norm == "CRITICAL":
                return "TRAFFIC_JAM"
            return norm
        return v


class TrafficDataResponse(BaseModel):
    id: int
    timestamp: datetime
    direction: str
    vehicle_count: int
    density_level: str
    speed_estimate: Optional[float] = None
    queue_length: float
    congestion_predicted: bool

    model_config = {"from_attributes": True}


class DirectionTrafficState(BaseModel):
    direction: str
    vehicle_count: int
    density_level: str
    density: float = 0.0
    speed_estimate: Optional[float] = None
    speed_is_estimate: bool = True
    queue_length: float = 0.0
    congestion_predicted: bool = False
    last_updated: Optional[datetime] = None


class AllTrafficStateResponse(BaseModel):
    north: Optional[DirectionTrafficState] = None
    south: Optional[DirectionTrafficState] = None
    east: Optional[DirectionTrafficState] = None
    west: Optional[DirectionTrafficState] = None
    timestamp: datetime


class TrafficHistoryRequest(BaseModel):
    direction: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
