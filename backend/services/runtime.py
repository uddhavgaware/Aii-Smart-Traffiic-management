"""
Application-wide singleton runtime holding SignalSafetyController,
TrafficIntelligenceEngine, EmergencyHandler, and configurable settings.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from core.config import settings
from core.database import db_session
from core.logging import get_logger
from core.redis_client import cache_set_signal_state
from models.signal_event import SignalEvent
from models.system_event import SystemEvent
from services.emergency_handler import EmergencyHandler
from services.mqtt_service import mqtt_service
from services.signal_controller import (
    Direction,
    SignalPhase,
    SignalSafetyController,
    ValidatedSignalCommand,
)
from services.traffic_intelligence import TrafficIntelligenceEngine
from services.websocket_manager import ws_manager

logger = get_logger(__name__)


class AppRuntime:
    """Holds initialized controllers and mutable runtime configuration."""

    def __init__(self) -> None:
        self.signal_controller = SignalSafetyController()
        self.traffic_engine = TrafficIntelligenceEngine(self.signal_controller)
        self.emergency_handler = EmergencyHandler(self.signal_controller)
        self.demo_mode: bool = settings.DEMO_MODE
        self.ai_engine_status: str = "stopped"
        self.last_inference_latency_ms: float = 0.0
        self.last_detection_fps: float = 0.0
        self.start_time: float = time.time()
        self.settings_store: dict[str, Any] = {
            "resolution": "720p",
            "fps_per_camera": 15,
            "density_thresholds": {
                "low": 5,
                "normal": 15,
                "medium": 25,
                "high": 40,
            },
            "mqtt_topic_prefix": settings.MQTT_TOPIC_PREFIX,
        }
        self._last_direction_durations: dict[str, int] = {
            d.value: 30 for d in Direction
        }

    async def on_validated_signal_command(self, cmd: ValidatedSignalCommand) -> None:
        """Called whenever SignalSafetyController emits a validated transition."""
        cmd_dict = cmd.as_dict()
        for d in ("north", "south", "east", "west"):
            self._last_direction_durations[d] = int(cmd.duration)

        # Publish to ESP32 via MQTT
        await mqtt_service.publish_signal_command(cmd_dict)

        # Cache full signal state in Redis
        full_state = self.get_signal_state_payload()
        await cache_set_signal_state(full_state)

        # Persist SignalEvent audit rows (for active non-red or all phase changes)
        try:
            async with db_session() as db:
                for d_enum, phase in (
                    (Direction.NORTH, cmd.north),
                    (Direction.SOUTH, cmd.south),
                    (Direction.EAST, cmd.east),
                    (Direction.WEST, cmd.west),
                ):
                    if phase != SignalPhase.RED or "all_red" in cmd.reason:
                        db.add(
                            SignalEvent(
                                direction=d_enum.value,
                                phase=phase.value,
                                duration=int(cmd.duration),
                                reason=cmd.reason[:255],
                                triggered_by=cmd.mode.value.lower(),
                                mode="MANUAL" if cmd.mode.value == "MANUAL" else "AUTO",
                            )
                        )
        except Exception as exc:
            logger.debug("signal_event_persist_skipped", error=str(exc))

    async def on_signal_broadcast(self, msg: dict[str, Any]) -> None:
        await ws_manager.broadcast("signal_update", self.get_signal_state_payload())
        explanation = self.traffic_engine.get_ai_explanation()
        if explanation:
            await ws_manager.broadcast(
                "ai_decision",
                {
                    "action": f"GREEN -> {', '.join(explanation['selected_pair']).upper()}",
                    "reason": explanation["explanation_text"],
                    "metrics": {
                        d: {
                            "count": explanation["metrics"].get("vehicle_count", 0),
                            "density": 0,
                            "queueLength": explanation["metrics"].get("queue_length", 0),
                        }
                        for d in explanation["selected_pair"]
                    },
                    "confidence": 0.9,
                    "algorithm": "Adaptive + Deterministic Safety Controller",
                },
            )

    def get_signal_state_payload(self) -> dict[str, Any]:
        raw = self.signal_controller.get_current_state()
        directions: dict[str, Any] = {}
        for d_name, st in raw["signals"].items():
            planned = self._last_direction_durations.get(d_name, 30)
            if st["phase"] == "YELLOW":
                planned = int(self.signal_controller.YELLOW_TIME)
            elif st["phase"] == "RED" and not raw["active_pair"]:
                planned = int(self.signal_controller.ALL_RED_TIME)
            remaining = max(0, int(round(planned - st["phase_elapsed"])))
            next_phase = "YELLOW" if st["phase"] == "GREEN" else ("RED" if st["phase"] == "YELLOW" else "GREEN")
            directions[d_name] = {
                "phase": st["phase"],
                "countdown": remaining,
                "time_remaining": remaining,
                "duration": planned,
                "recommended_green": planned,
                "next_phase": next_phase,
            }

        active_pair = raw["active_pair"]
        pair_label: Optional[str] = None
        if set(active_pair) == {"north", "south"}:
            pair_label = "NORTH_SOUTH"
        elif set(active_pair) == {"east", "west"}:
            pair_label = "EAST_WEST"

        return {
            "mode": raw["mode"],
            "active_pair": pair_label,
            "emergency_active": raw["emergency_active"],
            "emergency_direction": raw["emergency_direction"],
            "signals": directions,
            "directions": {
                d: {
                    "direction": d,
                    "phase": v["phase"],
                    "time_remaining": v["time_remaining"],
                    "duration": v["duration"],
                }
                for d, v in directions.items()
            },
        }

    async def log_system_event(self, event_type: str, severity: str, message: str) -> None:
        try:
            async with db_session() as db:
                db.add(SystemEvent(event_type=event_type, severity=severity, message=message))
        except Exception as exc:
            logger.debug("system_event_log_failed", error=str(exc))
        await ws_manager.broadcast(
            "notification",
            {"event_type": event_type, "severity": severity, "message": message},
        )


runtime = AppRuntime()
