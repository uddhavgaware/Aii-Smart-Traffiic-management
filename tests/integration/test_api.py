"""
Integration tests for FastAPI endpoints using TestClient and SQLite in-memory/temp DB.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_smarttraffic.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-integration-suite")
os.environ.setdefault("DEMO_MODE", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from main import app  # noqa: E402


def test_root_health():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


def test_unauthenticated_endpoints_rejected():
    with TestClient(app) as client:
        assert client.get("/api/signals/state").status_code == 401
        assert client.get("/api/cameras").status_code == 401
        assert client.get("/api/system/status").status_code == 401


def test_webrtc_config_accessible_for_mobile_pwa():
    with TestClient(app) as client:
        resp = client.get("/api/cameras/webrtc/config")
        assert resp.status_code == 200
        assert "ice_servers" in resp.json()
