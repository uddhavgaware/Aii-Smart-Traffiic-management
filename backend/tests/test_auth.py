"""Backend unit tests for JWT auth & password hashing."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.security import create_access_token, decode_token, hash_password, verify_password  # noqa: E402


def test_password_roundtrip():
    hashed = hash_password("StrongPass123!")
    assert verify_password("StrongPass123!", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_jwt_roundtrip():
    token = create_access_token("admin_user", "admin")
    payload = decode_token(token)
    assert payload["sub"] == "admin_user"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"
