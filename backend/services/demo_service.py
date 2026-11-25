"""
Clearly-labeled Demo Mode Service
=================================
Generates realistic synthetic traffic snapshots ONLY when runtime.demo_mode is True.
Per Strict Development Rule 24:
  - Demo mode must never be confused with real hardware operation.
  - When demo_mode is False, zero simulated counts/ESP32 status are produced.
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from typing import Optional

from core.logging import get_logger
from services.analytics_service import collect_host_performance
from services.runtime import runtime
from services.signal_controller import Direction
from services.traffic_intelligence import DensityLevel, DirectionTrafficData
from services.websocket_manager import ws_manager

logger = get_logger(__name__)


class DemoModeService:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("demo_mode_service_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("demo_mode_service_stopped")

    async def _loop(self) -> None:
        tick = 0
        while self._running:
            try:
                if runtime.demo_mode:
                    tick += 1
                    t = time.time()
                    for idx, d in enumerate(Direction):
                        base = int(8 + 14 * (0.5 + 0.5 * math.sin(tick * 0.25 + idx * 1.4)))
                        count = max(0, base + random.randint(-2, 3))
                        if count <= 5:
                            level = DensityLevel.LOW
                            density_pct = count * 4.0
                        elif count <= 15:
                            level = DensityLevel.NORMAL
                            density_pct = 25.0 + (count - 5) * 2.0
                        elif count <= 25:
                            level = DensityLevel.MEDIUM
                            density_pct = 48.0 + (count - 15) * 1.8
                        elif count <= 40:
                            level = DensityLevel.HIGH
                            density_pct = 68.0 + (count - 25) * 1.2
                        else:
                            level = DensityLevel.TRAFFIC_JAM
                            density_pct = 92.0

                        queue_len = round(min(100.0, count * 2.4), 1)
                        speed_est = round(max(1.5, 16.0 - count * 0.35), 1)

                        data = DirectionTrafficData(
                            direction=d,
                            vehicle_count=count,
                            density_level=level,
                            speed_estimate=speed_est,
                            speed_is_estimate=True,
                            queue_length=queue_len,
                            congestion_predicted=count > 22,
                            predicted_count=count + 2,
                            timestamp=t,
                        )
                        runtime.traffic_engine.update_direction_data(data)

                        await ws_manager.broadcast(
                            "traffic_update",
                            {
                                "direction": d.value,
                                "count": count,
                                "vehicle_count": count,
                                "speed": speed_est,
                                "speed_is_estimate": True,
                                "queue_length": queue_len,
                                "density": round(density_pct, 1),
                                "density_level": level,
                                "trend": "increasing" if count > 18 else "stable",
                                "congestion_predicted": count > 22,
                            },
                        )
                        await ws_manager.broadcast(
                            "camera_update",
                            {
                                "direction": d.value,
                                "vehicle_count": count,
                                "density": round(density_pct, 1),
                                "fps": 5.0,
                                "status": "connected",
                                "detections": [],
                            },
                        )

                    perf = collect_host_performance(inference_latency_ms=18.5, detection_fps=20.0)
                    await ws_manager.broadcast("performance_metrics", perf)
                    await ws_manager.broadcast("signal_update", runtime.get_signal_state_payload())

                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("demo_loop_error", error=str(exc))
                await asyncio.sleep(2.0)


demo_service = DemoModeService()
