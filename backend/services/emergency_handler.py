"""
Emergency Vehicle Intelligence Handler
======================================
Coordinates the 10-step emergency priority workflow when Stage 2 confirms
an ambulance or fire brigade vehicle (police vehicles are NOT given priority).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, update

from core.database import db_session
from core.logging import get_logger
from core.redis_client import cache_set_emergency_state
from models.emergency_event import EmergencyEvent
from services.signal_controller import Direction, SignalSafetyController
from services.websocket_manager import ws_manager

logger = get_logger(__name__)


class EmergencyHandler:
    """Manages emergency detection stages, signal override, clearance, and DB audit logging."""

    def __init__(self, signal_controller: SignalSafetyController) -> None:
        self.signal_controller = signal_controller
        self.active_event_id: Optional[int] = None
        self.active_direction: Optional[Direction] = None
        self.active_type: Optional[str] = None
        self.stage2_confirmed: bool = False
        self.confidence: float = 0.0
        self.first_detected: Optional[float] = None
        self.last_seen_at: Optional[float] = None

    async def process_alert(
        self,
        direction_str: str,
        vehicle_type: str,
        stage: int,
        confidence: float,
        cleared: bool = False,
    ) -> dict[str, Any]:
        """Handle incoming Stage 1 or Stage 2 emergency alert."""
        if vehicle_type not in ("ambulance", "fire_brigade"):
            return {"ignored": True, "reason": "Only ambulance and fire_brigade receive priority"}

        direction = Direction(direction_str)
        now = time.time()

        if cleared:
            return await self.clear_emergency(reason="Emergency vehicle cleared junction")

        is_stage2 = stage == 2 and confidence >= 0.7

        if self.active_event_id is None:
            self.first_detected = now
            self.active_direction = direction
            self.active_type = vehicle_type
            self.stage2_confirmed = is_stage2
            self.confidence = confidence
            self.last_seen_at = now

            try:
                async with db_session() as db:
                    ev = EmergencyEvent(
                        direction=direction.value,
                        vehicle_type=vehicle_type,
                        stage1_detected=True,
                        stage2_confirmed=is_stage2,
                        confidence=confidence,
                        signal_response="override_triggered" if is_stage2 else "monitoring_unconfirmed",
                    )
                    db.add(ev)
                    await db.flush()
                    await db.refresh(ev)
                    self.active_event_id = ev.id
            except Exception as exc:
                logger.warning("emergency_db_log_failed", error=str(exc))
        else:
            self.confidence = max(self.confidence, confidence)
            self.last_seen_at = now
            if is_stage2 and not self.stage2_confirmed:
                self.stage2_confirmed = True
                try:
                    async with db_session() as db:
                        await db.execute(
                            update(EmergencyEvent)
                            .where(EmergencyEvent.id == self.active_event_id)
                            .values(
                                stage2_confirmed=True,
                                confidence=self.confidence,
                                signal_response="override_triggered",
                            )
                        )
                except Exception as exc:
                    logger.warning("emergency_db_update_failed", error=str(exc))

        if is_stage2 and not self.signal_controller.emergency_active:
            await self.signal_controller.emergency_override(direction, vehicle_type)

        state = self.get_current_state()
        await cache_set_emergency_state(state)
        await ws_manager.broadcast("emergency_alert", {
            "active": True,
            "type": self.active_type,
            "vehicle_type": self.active_type,
            "direction": direction.value,
            "confidence": self.confidence,
            "status": "stage2_confirmed" if self.stage2_confirmed else "stage1_confirmed",
            "first_detected": int((self.first_detected or now) * 1000),
        })
        return state

    async def clear_emergency(self, remaining_queue: float = 0.0, reason: str = "Cleared") -> dict[str, Any]:
        """Step 8-12: Clear emergency, extend green if queue remains, resume normal control."""
        additional_green = 15.0 if remaining_queue > 50.0 else None
        if self.signal_controller.emergency_active:
            await self.signal_controller.clear_emergency(additional_green=additional_green)

        if self.active_event_id is not None:
            try:
                async with db_session() as db:
                    await db.execute(
                        update(EmergencyEvent)
                        .where(EmergencyEvent.id == self.active_event_id)
                        .values(
                            cleared_at=datetime.now(timezone.utc),
                            signal_response=reason,
                        )
                    )
            except Exception as exc:
                logger.warning("emergency_db_clear_failed", error=str(exc))

        self.active_event_id = None
        self.active_direction = None
        self.active_type = None
        self.stage2_confirmed = False
        self.confidence = 0.0
        self.first_detected = None

        await cache_set_emergency_state(None)
        await ws_manager.broadcast("emergency_alert", {
            "active": False,
            "type": None,
            "direction": None,
            "confidence": 0.0,
            "status": "cleared",
        })
        return self.get_current_state()

    def get_current_state(self) -> dict[str, Any]:
        if self.active_direction is None:
            return {
                "status": "none",
                "active_event": None,
                "affected_direction": None,
                "countdown_seconds": None,
            }
        return {
            "status": "stage2_confirmed" if self.stage2_confirmed else "stage1_detected",
            "affected_direction": self.active_direction.value,
            "vehicle_type": self.active_type,
            "confidence": self.confidence,
            "first_detected": self.first_detected,
        }
