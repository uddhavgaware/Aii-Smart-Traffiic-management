"""
Camera registration, QR pairing generation, and WebRTC signaling state.
"""

from __future__ import annotations

import io
import json
import secrets
import time
from typing import Any, Dict

import qrcode

from core.config import settings


class CameraRegistry:
    """Manages unique camera IDs, QR code generation, and pairing codes."""

    def __init__(self) -> None:
        self._junction_code: str = self._new_code()
        self._code_generated_at: float = time.time()
        self._code_ttl: int = 3600
        self.webrtc_offers: Dict[str, dict[str, Any]] = {}
        self.webrtc_answers: Dict[str, dict[str, Any]] = {}
        self.ice_candidates: Dict[str, list[dict[str, Any]]] = {}

    @staticmethod
    def _new_code() -> str:
        return f"JCT-{settings.JUNCTION_ID[-3:].upper()}-{secrets.token_hex(3).upper()}"

    def get_junction_code(self, force_refresh: bool = False) -> dict[str, Any]:
        elapsed = time.time() - self._code_generated_at
        if force_refresh or elapsed >= self._code_ttl:
            self._junction_code = self._new_code()
            self._code_generated_at = time.time()
            elapsed = 0
        return {
            "code": self._junction_code,
            "expires_in": max(0, int(self._code_ttl - elapsed)),
        }

    def generate_unique_id(self, direction: str) -> str:
        return f"cam_{direction}_{secrets.token_hex(4)}"

    def generate_qr_code(self, payload: dict[str, Any]) -> bytes:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(json.dumps(payload))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


camera_registry = CameraRegistry()
