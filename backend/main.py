"""
FastAPI Backend Application Entry Point
=====================================
Initializes Database, Redis, MQTT TLS client, SignalSafetyController,
TrafficIntelligenceEngine, and DemoModeService.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api import analytics, auth, cameras, emergency, hardware, signals, system, traffic
from core.config import settings
from core.database import close_db, db_session, init_db
from core.logging import configure_logging, get_logger
from core.redis_client import close_redis, init_redis
from core.security import hash_password
from middleware.rate_limit import limiter
from models.user import User
from sqlalchemy import select
from services.analytics_service import collect_host_performance
from services.demo_service import demo_service
from services.mqtt_service import mqtt_service
from services.runtime import runtime
from services.websocket_manager import ws_manager
from websocket.handler import websocket_endpoint

configure_logging(debug=settings.DEBUG)
logger = get_logger(__name__)

_telemetry_task: asyncio.Task | None = None


async def _telemetry_broadcaster() -> None:
    """Broadcast real measured CPU/GPU/VRAM and countdown telemetry every 2s."""
    while True:
        try:
            await asyncio.sleep(2.0)
            if ws_manager.connection_count > 0:
                perf = collect_host_performance(
                    inference_latency_ms=runtime.last_inference_latency_ms,
                    detection_fps=runtime.last_detection_fps,
                )
                await ws_manager.broadcast("performance_metrics", perf)
                await ws_manager.broadcast("signal_update", runtime.get_signal_state_payload())
                await ws_manager.broadcast("esp32_status", mqtt_service.get_status())
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug("telemetry_broadcaster_error", error=str(exc))


async def _ensure_initial_admin() -> None:
    """Create initial admin user on fresh cloud databases when ADMIN_PASSWORD env var is set."""
    if not settings.ADMIN_PASSWORD:
        return
    try:
        async with db_session() as db:
            existing = (
                await db.execute(select(User).where(User.username == settings.ADMIN_USERNAME))
            ).scalar_one_or_none()
            if not existing:
                db.add(
                    User(
                        username=settings.ADMIN_USERNAME,
                        email=settings.ADMIN_EMAIL,
                        hashed_password=hash_password(settings.ADMIN_PASSWORD),
                        role="admin",
                        is_active=True,
                    )
                )
                logger.info("initial_admin_created", username=settings.ADMIN_USERNAME)
    except Exception as exc:
        logger.warning("initial_admin_bootstrap_skipped", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _telemetry_task
    logger.info("smart_traffic_backend_starting", junction=settings.JUNCTION_ID)

    # 1. Database & Redis
    try:
        await init_db()
        await _ensure_initial_admin()
    except Exception as exc:
        logger.warning("db_init_deferred", error=str(exc))
    await init_redis()

    # 2. Wire SignalSafetyController callbacks -> MQTT + WebSocket
    runtime.signal_controller.set_command_callback(runtime.on_validated_signal_command)
    runtime.signal_controller.set_broadcast_callback(runtime.on_signal_broadcast)

    # 3. MQTT broker bridge
    loop = asyncio.get_running_loop()

    async def _on_esp32_status(st: dict[str, Any]) -> None:
        await ws_manager.broadcast("esp32_status", st)

    mqtt_service.set_status_callback(_on_esp32_status)
    mqtt_service.start(loop)

    # 4. Start SignalSafetyController, TrafficIntelligenceEngine, DemoService, Telemetry
    await runtime.signal_controller.start()
    await runtime.traffic_engine.start()
    await demo_service.start()
    _telemetry_task = asyncio.create_task(_telemetry_broadcaster())

    yield

    logger.info("smart_traffic_backend_shutting_down")
    if _telemetry_task:
        _telemetry_task.cancel()
    await demo_service.stop()
    await runtime.traffic_engine.stop()
    await runtime.signal_controller.stop()
    mqtt_service.stop()
    await close_redis()
    await close_db()


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Register API routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(cameras.router, prefix=settings.API_PREFIX)
app.include_router(traffic.router, prefix=settings.API_PREFIX)
app.include_router(signals.router, prefix=settings.API_PREFIX)
app.include_router(emergency.router, prefix=settings.API_PREFIX)
app.include_router(analytics.router, prefix=settings.API_PREFIX)
app.include_router(system.router, prefix=settings.API_PREFIX)
app.include_router(hardware.router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["Health"])
async def root_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "junction_id": settings.JUNCTION_ID,
    }


@app.websocket("/ws")
async def ws_route(websocket: WebSocket) -> None:
    await websocket_endpoint(websocket)
