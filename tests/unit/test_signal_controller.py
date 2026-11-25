"""
Unit tests for deterministic SignalSafetyController.
Verifies:
  1. Never allows conflicting perpendicular greens (N/S vs E/W)
  2. Clamps green durations to [MIN_GREEN_TIME, MAX_GREEN_TIME]
  3. Safe transition sequence (GREEN -> YELLOW -> ALL_RED -> GREEN)
  4. Starvation prevention detection when wait time > MAX_WAIT_TIME
  5. Emergency override workflow
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from services.signal_controller import (  # noqa: E402
    COMPATIBLE_PAIRS,
    Direction,
    SignalMode,
    SignalPhase,
    SignalRecommendation,
    SignalSafetyController,
)


def test_no_conflicting_greens():
    ctrl = SignalSafetyController()
    with pytest.raises(ValueError):
        ctrl._verify_no_conflict(frozenset({Direction.NORTH, Direction.EAST}))

    # Invalid pair corrected to valid pair during validation
    corrected = ctrl._validate_pair(frozenset({Direction.NORTH, Direction.EAST}))
    assert corrected in COMPATIBLE_PAIRS


def test_duration_clamping():
    ctrl = SignalSafetyController(min_green=15.0, max_green=120.0)
    assert ctrl._clamp_duration(3.0) == 15.0
    assert ctrl._clamp_duration(45.0) == 45.0
    assert ctrl._clamp_duration(300.0) == 120.0


def test_starvation_prevention():
    ctrl = SignalSafetyController(max_wait=180.0)
    ctrl.states[Direction.EAST].phase = SignalPhase.RED
    ctrl.states[Direction.EAST].wait_start_time = time.time() - 185.0
    assert ctrl._check_starvation() == Direction.EAST


def test_safe_transition_sequence():
    async def _run():
        ctrl = SignalSafetyController(min_green=15.0, yellow_time=0.05, all_red_time=0.05)
        commands = []

        async def capture(cmd):
            commands.append(cmd)

        ctrl.set_command_callback(capture)
        await ctrl._apply_green(frozenset({Direction.NORTH, Direction.SOUTH}), 15.0, "init")
        await ctrl.manual_command(frozenset({Direction.EAST, Direction.WEST}), 20.0, "admin")

        phases = [(c.north, c.east) for c in commands]
        # Must transition through N=GREEN/E=RED -> N=YELLOW/E=RED -> ALL RED -> N=RED/E=GREEN
        assert phases[0] == (SignalPhase.GREEN, SignalPhase.RED)
        assert phases[1] == (SignalPhase.YELLOW, SignalPhase.RED)
        assert phases[2] == (SignalPhase.RED, SignalPhase.RED)
        assert phases[3] == (SignalPhase.RED, SignalPhase.GREEN)

    asyncio.run(_run())


def test_emergency_override_and_clear():
    async def _run():
        ctrl = SignalSafetyController(yellow_time=0.05, all_red_time=0.05)
        commands = []

        async def capture(cmd):
            commands.append(cmd)

        ctrl.set_command_callback(capture)
        await ctrl._apply_green(frozenset({Direction.NORTH, Direction.SOUTH}), 20.0, "normal")
        await ctrl.emergency_override(Direction.WEST, "ambulance")

        assert ctrl.emergency_active is True
        assert ctrl.current_mode == SignalMode.EMERGENCY
        assert ctrl.states[Direction.WEST].phase == SignalPhase.GREEN
        assert ctrl.states[Direction.NORTH].phase == SignalPhase.RED

        await ctrl.clear_emergency()
        assert ctrl.emergency_active is False
        assert ctrl.current_mode == SignalMode.AUTO

    asyncio.run(_run())
