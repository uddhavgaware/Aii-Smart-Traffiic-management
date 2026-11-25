"""
Signal Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SignalPhase(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class SignalMode(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


class DirectionSignalState(BaseModel):
    direction: str
    phase: SignalPhase
    time_remaining: int  # seconds
    duration: int        # planned duration in seconds


class SignalStateResponse(BaseModel):
    mode: SignalMode
    active_pair: Optional[str] = None  # e.g. "NORTH_SOUTH" or "EAST_WEST"
    directions: Dict[str, DirectionSignalState]
    timestamp: datetime
    emergency_active: bool = False


class SignalCommandRequest(BaseModel):
    """Manual signal command (admin only)."""
    direction: str = Field(..., pattern="^(north|south|east|west)$")
    phase: SignalPhase
    duration: int = Field(..., ge=5, le=300)
    reason: Optional[str] = Field(None, max_length=255)


class SignalConfigRequest(BaseModel):
    min_green_time: int = Field(15, ge=5, le=60)
    max_green_time: int = Field(120, ge=30, le=300)
    yellow_time: int = Field(3, ge=2, le=10)
    all_red_time: int = Field(2, ge=1, le=10)
    max_wait_time: int = Field(180, ge=60, le=600)


class SignalConfigResponse(SignalConfigRequest):
    updated_at: Optional[datetime] = None


class SignalModeRequest(BaseModel):
    mode: SignalMode
    reason: Optional[str] = Field(None, max_length=255)


class SignalHistoryItem(BaseModel):
    id: int
    timestamp: datetime
    direction: str
    phase: str
    duration: int
    reason: str
    triggered_by: str
    mode: str

    model_config = {"from_attributes": True}
