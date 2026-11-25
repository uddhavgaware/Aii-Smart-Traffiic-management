"""Backend unit tests for CameraRegistry."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.camera_registry import CameraRegistry  # noqa: E402


def test_qr_and_unique_id_generation():
    reg = CameraRegistry()
    cid = reg.generate_unique_id("north")
    assert cid.startswith("cam_north_")
    png = reg.generate_qr_code({"direction": "north", "camera_id": cid})
    assert png.startswith(b"\x89PNG")
