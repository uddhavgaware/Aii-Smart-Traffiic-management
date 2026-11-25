"""Backend unit tests for SignalSafetyController."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.signal_controller import Direction, SignalSafetyController  # noqa: E402


def test_compatible_pairs():
    ctrl = SignalSafetyController()
    ns = ctrl._get_pair_for_direction(Direction.NORTH)
    assert ns == frozenset({Direction.NORTH, Direction.SOUTH})
    ew = ctrl._get_pair_for_direction(Direction.EAST)
    assert ew == frozenset({Direction.EAST, Direction.WEST})
