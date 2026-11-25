"""
Application configuration loaded from environment variables via Pydantic Settings.
"""

from __future__ import annotations

import json
from typing import List, Union

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/smarttraffic"
    DB_POOL_MIN_SIZE: int = 5
    DB_POOL_MAX_SIZE: int = 20
    DB_POOL_TIMEOUT: int = 30

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_POOL_SIZE: int = 10

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-this-in-production-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── MQTT ──────────────────────────────────────────────────────────────────
    MQTT_BROKER: str = "localhost"
    MQTT_PORT: int = 8883
    MQTT_USERNAME: str = "traffic_system"
    MQTT_PASSWORD: str = ""
    MQTT_USE_TLS: bool = True
    MQTT_TOPIC_PREFIX: str = "smarttraffic/junction1"
    MQTT_KEEPALIVE: int = 60
    MQTT_QOS: int = 1

    # ── ML Inference ──────────────────────────────────────────────────────────
    ML_INFERENCE_URL: str = "http://127.0.0.1:8001"
    ML_API_KEY: str = ""
    ML_TIMEOUT_SECONDS: int = 10

    # ── WebRTC / STUN / TURN ──────────────────────────────────────────────────
    TURN_SERVER_URL: str = "turn:your-turn-server.com:3478"
    TURN_USERNAME: str = ""
    TURN_CREDENTIAL: str = ""
    STUN_SERVER_URL: str = "stun:stun.l.google.com:19302"

    # ── App ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]
    DEMO_MODE: bool = False
    JUNCTION_ID: str = "junction_001"
    API_PREFIX: str = "/api"
    APP_TITLE: str = "Smart Traffic Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 100

    # ── Initial Admin Bootstrap (optional for cloud PaaS first-boot) ──────────
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@smarttraffic.local"
    ADMIN_PASSWORD: str = ""

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return "postgresql+asyncpg://" + v[len("postgres://"):]
            if v.startswith("postgresql://") and "+asyncpg" not in v:
                return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            # Try JSON parse first, then comma-split
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def mqtt_signal_command_topic(self) -> str:
        return f"{self.MQTT_TOPIC_PREFIX}/signals/command"

    @property
    def mqtt_signal_ack_topic(self) -> str:
        return f"{self.MQTT_TOPIC_PREFIX}/signals/ack"

    @property
    def mqtt_status_topic(self) -> str:
        return f"{self.MQTT_TOPIC_PREFIX}/status"

    @property
    def mqtt_error_topic(self) -> str:
        return f"{self.MQTT_TOPIC_PREFIX}/error"


settings = Settings()
