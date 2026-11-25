"""
Emergency Pydantic schemas.
Note: Police vehicles are explicitly excluded from emergency signal priority.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EmergencyStatus(str, Enum):
    NONE = "none"
    STAGE1_DETECTED = "stage1_detected"
    STAGE2_CONFIRMED = "stage2_confirmed"
    SIGNAL_GRANTED = "signal_granted"
    CLEARED = "cleared"


class EmergencyVehicleType(str, Enum):
    AMBULANCE = "ambulance"
    FIRE_BRIGADE = "fire_brigade"


class EmergencyAlertRequest(BaseModel):
    """Payload from ML service when an ambulance or fire brigade is detected."""
    direction: str = Field(..., pattern="^(north|south|east|west)$")
    vehicle_type: EmergencyVehicleType
    stage: int = Field(..., ge=1, le=2)  # 1 = vehicle detected, 2 = flashing beacons confirmed
    confidence: float = Field(..., ge=0.0, le=1.0)
    cleared: bool = False
    timestamp: Optional[datetime] = None


class EmergencyEventResponse(BaseModel):
    id: int
    timestamp: datetime
    direction: str
    vehicle_type: str
    stage1_detected: bool
    stage2_confirmed: bool
    confidence: float
    cleared_at: Optional[datetime] = None
    signal_response: Optional[str] = None

    model_config = {"from_attributes": True}


class EmergencyClearRequest(BaseModel):
    event_id: Optional[int] = None
    reason: Optional[str] = None


class CurrentEmergencyState(BaseModel):
    status: EmergencyStatus
    active_event: Optional[EmergencyEventResponse] = None
    affected_direction: Optional[str] = None
    countdown_seconds: Optional[int] = None
