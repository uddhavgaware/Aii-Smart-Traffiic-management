"""Backend unit tests for EmergencyHandler."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.emergency_handler import EmergencyHandler  # noqa: E402
from services.signal_controller import SignalSafetyController  # noqa: E402


def test_police_ignored_for_emergency_priority():
    async def _run():
        ctrl = SignalSafetyController()
        handler = EmergencyHandler(ctrl)
        res = await handler.process_alert("north", "police", stage=2, confidence=0.99)
        assert res.get("ignored") is True
        assert ctrl.emergency_active is False

    asyncio.run(_run())
