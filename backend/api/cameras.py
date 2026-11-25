"""
Camera API routes including QR pairing, manual registration, status, and WebRTC STUN/TURN config.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.logging import get_logger
from middleware.auth import get_current_user, require_role
from models.camera import Camera
from models.user import User
from schemas.camera import (
    CameraRegisterRequest,
    CameraResponse,
    CameraUpdateRequest,
    ICEServerConfig,
    WebRTCAnswerRequest,
    WebRTCConfigResponse,
    WebRTCIceRequest,
    WebRTCOfferRequest,
)
from services.camera_registry import camera_registry
from services.runtime import runtime
from services.websocket_manager import ws_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("", response_model=List[CameraResponse])
async def list_cameras(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[CameraResponse]:
    """List all registered cameras."""
    result = await db.execute(select(Camera).order_by(Camera.direction))
    cameras = result.scalars().all()
    return [CameraResponse.model_validate(c) for c in cameras]


@router.get("/junction-code")
async def get_junction_code(
    refresh: bool = False,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current pairing code for QR/manual camera onboarding."""
    return camera_registry.get_junction_code(force_refresh=refresh)


@router.get("/webrtc/config", response_model=WebRTCConfigResponse)
async def get_webrtc_config() -> WebRTCConfigResponse:
    """Return STUN/TURN ICE server configuration (allows mobile camera PWA pairing)."""
    servers = [ICEServerConfig(urls=[settings.STUN_SERVER_URL])]
    if settings.TURN_SERVER_URL:
        servers.append(
            ICEServerConfig(
                urls=[settings.TURN_SERVER_URL],
                username=settings.TURN_USERNAME or None,
                credential=settings.TURN_CREDENTIAL or None,
            )
        )
    return WebRTCConfigResponse(ice_servers=servers)


@router.post("/register", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def register_camera(
    payload: CameraRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> CameraResponse:
    """
    Register a mobile camera for a direction.
    Prevents duplicate direction assignment unless allow_replace is explicitly True.
    Accepts either authenticated dashboard users or mobile QR pairing code.
    """
    result = await db.execute(select(Camera).where(Camera.direction == payload.direction))
    existing = result.scalar_one_or_none()
    if existing:
        if not payload.allow_replace:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Camera for direction '{payload.direction}' already registered. Admin overwrite required.",
            )
        existing.unique_id = payload.device_id or camera_registry.generate_unique_id(payload.direction)
        existing.stream_url = payload.stream_url
        existing.ip_address = payload.ip_address
        existing.status = "connecting"
        existing.last_seen = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(existing)
        await runtime.log_system_event(
            "camera_registered", "info", f"Camera reassigned for {payload.direction} ({existing.unique_id})"
        )
        return CameraResponse.model_validate(existing)

    unique_id = payload.device_id or camera_registry.generate_unique_id(payload.direction)
    camera = Camera(
        unique_id=unique_id,
        direction=payload.direction,
        status="connecting",
        stream_url=payload.stream_url,
        ip_address=payload.ip_address,
        last_seen=datetime.now(timezone.utc),
    )
    db.add(camera)
    await db.flush()
    await db.refresh(camera)

    await runtime.log_system_event(
        "camera_registered", "info", f"Camera registered for {payload.direction} ({unique_id})"
    )
    logger.info("camera_registered", direction=payload.direction, unique_id=unique_id)
    return CameraResponse.model_validate(camera)


@router.get("/qr/{direction}")
async def get_qr_code(
    direction: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Generate a PNG QR code for mobile camera pairing."""
    if direction not in ("north", "south", "east", "west"):
        raise HTTPException(status_code=400, detail="Invalid direction")

    result = await db.execute(select(Camera).where(Camera.direction == direction))
    camera = result.scalar_one_or_none()
    code_info = camera_registry.get_junction_code()

    qr_data = {
        "direction": direction,
        "camera_id": camera.unique_id if camera else None,
        "junction_id": settings.JUNCTION_ID,
        "junction_code": code_info["code"],
    }
    img_bytes = camera_registry.generate_qr_code(qr_data)
    return StreamingResponse(io.BytesIO(img_bytes), media_type="image/png")


@router.get("/{direction}/status")
async def get_direction_camera_status(
    direction: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if direction not in ("north", "south", "east", "west"):
        raise HTTPException(status_code=400, detail="Invalid direction")
    result = await db.execute(select(Camera).where(Camera.direction == direction))
    camera = result.scalar_one_or_none()
    if not camera:
        return {"direction": direction, "registered": False, "status": "offline"}
    return {
        "direction": direction,
        "registered": True,
        "unique_id": camera.unique_id,
        "status": camera.status,
        "last_seen": camera.last_seen.isoformat() if camera.last_seen else None,
    }


@router.get("/{target}", response_model=CameraResponse)
async def get_camera(
    target: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CameraResponse:
    """Get camera details by numeric ID or direction."""
    if target in ("north", "south", "east", "west"):
        stmt = select(Camera).where(Camera.direction == target)
    elif target.isdigit():
        stmt = select(Camera).where(Camera.id == int(target))
    else:
        raise HTTPException(status_code=400, detail="Invalid camera identifier")
    camera = (await db.execute(stmt)).scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return CameraResponse.model_validate(camera)


@router.post("/{target}/reconnect", status_code=status.HTTP_202_ACCEPTED)
async def reconnect_camera(
    target: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "operator")),
) -> dict:
    """Trigger reconnect by direction ('north'..'west') or numeric camera ID."""
    if target in ("north", "south", "east", "west"):
        stmt = select(Camera).where(Camera.direction == target)
    else:
        stmt = select(Camera).where(Camera.id == int(target))
    camera = (await db.execute(stmt)).scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    camera.status = "connecting"
    await db.flush()
    await ws_manager.broadcast("camera_reconnect", {"direction": camera.direction, "camera_id": camera.unique_id})
    return {"message": "Reconnect triggered", "direction": camera.direction, "camera_id": camera.id}


@router.delete("/{target}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_camera(
    target: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
) -> Response:
    """Unregister a camera by direction or ID."""
    if target in ("north", "south", "east", "west"):
        stmt = select(Camera).where(Camera.direction == target)
    else:
        stmt = select(Camera).where(Camera.id == int(target))
    camera = (await db.execute(stmt)).scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    direction = camera.direction
    await db.delete(camera)
    await ws_manager.broadcast("camera_disconnected", {"direction": direction})
    logger.info("camera_deleted", direction=direction)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: int,
    payload: CameraUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "operator")),
) -> CameraResponse:
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(camera, field, value)

    await db.flush()
    await db.refresh(camera)
    return CameraResponse.model_validate(camera)


@router.post("/webrtc/offer")
async def webrtc_offer(payload: WebRTCOfferRequest) -> dict:
    camera_registry.webrtc_offers[payload.camera_id] = payload.model_dump()
    await ws_manager.broadcast("webrtc_offer", payload.model_dump())
    return {"status": "offer_relayed", "camera_id": payload.camera_id}


@router.post("/webrtc/answer")
async def webrtc_answer(payload: WebRTCAnswerRequest) -> dict:
    camera_registry.webrtc_answers[payload.camera_id] = payload.model_dump()
    await ws_manager.broadcast("webrtc_answer", payload.model_dump())
    return {"status": "answer_relayed", "camera_id": payload.camera_id}


@router.post("/webrtc/ice")
async def webrtc_ice(payload: WebRTCIceRequest) -> dict:
    camera_registry.ice_candidates.setdefault(payload.camera_id, []).append(payload.model_dump())
    await ws_manager.broadcast("webrtc_ice", payload.model_dump())
    return {"status": "ice_relayed", "camera_id": payload.camera_id}
