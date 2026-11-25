"""
Camera Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CameraRegisterRequest(BaseModel):
    direction: str = Field(..., pattern="^(north|south|east|west)$")
    junction_code: Optional[str] = None
    device_id: Optional[str] = None
    allow_replace: bool = False
    stream_url: Optional[str] = None
    ip_address: Optional[str] = None


class CameraUpdateRequest(BaseModel):
    stream_url: Optional[str] = None
    ip_address: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(online|offline|connecting|error)$")


class CameraResponse(BaseModel):
    id: int
    unique_id: str
    direction: str
    status: str
    stream_url: Optional[str] = None
    ip_address: Optional[str] = None
    registered_at: datetime
    last_seen: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WebRTCOfferRequest(BaseModel):
    camera_id: str
    direction: Optional[str] = None
    sdp: str
    type: str = "offer"


class WebRTCAnswerRequest(BaseModel):
    camera_id: str
    direction: Optional[str] = None
    sdp: str
    type: str = "answer"


class WebRTCIceRequest(BaseModel):
    camera_id: str
    direction: Optional[str] = None
    candidate: str
    sdp_mid: Optional[str] = None
    sdp_mline_index: Optional[int] = None


class ICEServerConfig(BaseModel):
    urls: list[str]
    username: Optional[str] = None
    credential: Optional[str] = None


class WebRTCConfigResponse(BaseModel):
    ice_servers: list[ICEServerConfig]
