"""
Signal Safety Controller
========================
DETERMINISTIC safety layer — independent of ML model.
The ML model RECOMMENDS signal timing.
This controller VALIDATES and EXECUTES decisions.

Safety rules (non-negotiable):
  - GREEN → YELLOW → ALL-RED → NEXT GREEN (always)
  - No conflicting greens ever
  - Compatible pairs: (NORTH+SOUTH) or (EAST+WEST)
  - MIN_GREEN_TIME ≤ green ≤ MAX_GREEN_TIME
  - Starvation prevention: no direction waits > MAX_WAIT_TIME
  - Emergency override uses safe 10-step workflow
"""

import asyncio
import logging
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class SignalPhase(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class Direction(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class SignalMode(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"


# Compatible direction pairs that can share GREEN simultaneously
COMPATIBLE_PAIRS = [
    frozenset({Direction.NORTH, Direction.SOUTH}),
    frozenset({Direction.EAST, Direction.WEST}),
]

# Cycle order
SIGNAL_CYCLE = [
    frozenset({Direction.NORTH, Direction.SOUTH}),
    frozenset({Direction.EAST, Direction.WEST}),
]


@dataclass
class SignalState:
    phase: SignalPhase = SignalPhase.RED
    phase_start_time: float = field(default_factory=time.time)
    last_green_time: float = 0.0
    wait_start_time: float = field(default_factory=time.time)

    @property
    def phase_elapsed(self) -> float:
        return time.time() - self.phase_start_time

    @property
    def wait_elapsed(self) -> float:
        return time.time() - self.wait_start_time


@dataclass
class SignalRecommendation:
    """ML model recommendation (not yet validated)."""
    active_pair: frozenset  # directions to get GREEN
    green_duration: float   # recommended seconds
    reason: str
    emergency_direction: Optional[Direction] = None
    is_emergency: bool = False


@dataclass
class ValidatedSignalCommand:
    """Safety-validated command ready for MQTT/ESP32."""
    north: SignalPhase
    south: SignalPhase
    east: SignalPhase
    west: SignalPhase
    duration: float
    sequence_id: int
    mode: SignalMode
    reason: str

    def as_dict(self) -> dict:
        return {
            "cmd": "set_phase",
            "sequence_id": self.sequence_id,
            "mode": self.mode.value,
            "signals": {
                "north": {"phase": self.north.value, "duration": int(self.duration)},
                "south": {"phase": self.south.value, "duration": int(self.duration)},
                "east":  {"phase": self.east.value,  "duration": int(self.duration)},
                "west":  {"phase": self.west.value,  "duration": int(self.duration)},
            },
            "reason": self.reason,
        }


class SignalSafetyController:
    """
    Deterministic signal safety controller.
    
    Runs as an async loop. Receives recommendations from Traffic Intelligence.
    Enforces all safety rules before commanding ESP32.
    
    NEVER lets the ML model bypass safety constraints.
    """

    # Safety timing constants (seconds) — can be overridden via config
    MIN_GREEN_TIME: float = 15.0
    MAX_GREEN_TIME: float = 120.0
    YELLOW_TIME: float = 3.0
    ALL_RED_TIME: float = 2.0
    MAX_WAIT_TIME: float = 180.0  # starvation prevention

    def __init__(
        self,
        min_green: float = 15.0,
        max_green: float = 120.0,
        yellow_time: float = 3.0,
        all_red_time: float = 2.0,
        max_wait: float = 180.0,
    ):
        self.MIN_GREEN_TIME = min_green
        self.MAX_GREEN_TIME = max_green
        self.YELLOW_TIME = yellow_time
        self.ALL_RED_TIME = all_red_time
        self.MAX_WAIT_TIME = max_wait

        # State per direction
        self.states: dict[Direction, SignalState] = {
            d: SignalState() for d in Direction
        }

        # Current active green pair
        self.active_pair: frozenset = frozenset()
        self.cycle_index: int = 0

        # Transition state
        self.in_transition: bool = False
        self.current_mode: SignalMode = SignalMode.AUTO
        self.pending_recommendation: Optional[SignalRecommendation] = None

        # Sequence counter for MQTT
        self._sequence_id: int = 0

        # Emergency state
        self.emergency_direction: Optional[Direction] = None
        self.emergency_active: bool = False

        # Callback to send validated command to MQTT
        self._command_callback: Optional[Callable[[ValidatedSignalCommand], Awaitable[None]]] = None
        # Callback to broadcast state via WebSocket
        self._broadcast_callback: Optional[Callable[[dict], Awaitable[None]]] = None

        # Running flag
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

        logger.info(
            "SignalSafetyController initialized",
            extra={
                "min_green": self.MIN_GREEN_TIME,
                "max_green": self.MAX_GREEN_TIME,
                "yellow": self.YELLOW_TIME,
                "all_red": self.ALL_RED_TIME,
            }
        )

    def set_command_callback(self, cb: Callable[[ValidatedSignalCommand], Awaitable[None]]):
        self._command_callback = cb

    def set_broadcast_callback(self, cb: Callable[[dict], Awaitable[None]]):
        self._broadcast_callback = cb

    async def start(self):
        """Start the signal control loop."""
        self._running = True
        # Initial state: ALL RED
        await self._apply_all_red("system_startup")
        self._task = asyncio.create_task(self._control_loop())
        logger.info("Signal safety controller started")

    async def stop(self):
        """Stop the signal control loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Signal safety controller stopped")

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def accept_recommendation(self, recommendation: SignalRecommendation):
        """
        Accept a signal recommendation from the Traffic Intelligence engine.
        The recommendation will be applied at the next safe opportunity.
        Does NOT immediately switch signals.
        """
        if self.current_mode != SignalMode.AUTO:
            logger.debug("Ignoring ML recommendation — not in AUTO mode")
            return

        # Validate the recommendation
        validated_pair = self._validate_pair(recommendation.active_pair)
        validated_duration = self._clamp_duration(recommendation.green_duration)

        self.pending_recommendation = SignalRecommendation(
            active_pair=validated_pair,
            green_duration=validated_duration,
            reason=recommendation.reason,
        )
        logger.debug(
            "Recommendation accepted",
            extra={"pair": str(validated_pair), "duration": validated_duration}
        )

    async def emergency_override(self, direction: Direction, emergency_type: str):
        """
        10-step emergency signal workflow.
        Called by EmergencyHandler when Stage 2 confirms emergency.
        """
        if self.emergency_active:
            logger.warning("Emergency already active — ignoring new override request")
            return

        logger.warning(
            "EMERGENCY OVERRIDE INITIATED",
            extra={"direction": direction.value, "type": emergency_type}
        )

        self.emergency_active = True
        self.emergency_direction = direction
        self.current_mode = SignalMode.EMERGENCY

        # Step 1–3: Identify direction and current phase
        logger.info(f"Emergency Step 1-3: Direction={direction.value}, Type={emergency_type}")

        # Step 4: End current green phase (if any) — set target to 0
        # Step 5: Activate YELLOW
        if self.active_pair:
            logger.info("Emergency Step 4-5: Transitioning current green to YELLOW")
            await self._apply_yellow(self.active_pair, f"emergency_clearance_{emergency_type}")
            await asyncio.sleep(self.YELLOW_TIME)

        # Step 6: ALL-RED clearance
        logger.info("Emergency Step 6: ALL-RED clearance period")
        await self._apply_all_red(f"emergency_all_red_{emergency_type}")
        await asyncio.sleep(self.ALL_RED_TIME)

        # Step 7: Activate GREEN for emergency direction
        # Include compatible partner direction
        emergency_pair = self._get_pair_for_direction(direction)
        logger.info(f"Emergency Step 7: GREEN for {[d.value for d in emergency_pair]}")
        await self._apply_green(emergency_pair, self.MAX_GREEN_TIME, f"emergency_{emergency_type}")

        # Steps 8–10 are handled by EmergencyHandler which monitors vehicle clearance
        # and calls clear_emergency() when done

    async def clear_emergency(self, additional_green: Optional[float] = None):
        """
        Called when emergency vehicle has cleared junction.
        Resumes normal adaptive operation.
        """
        if not self.emergency_active:
            return

        logger.info("Emergency cleared — resuming normal operation")

        # Give additional green if queue remains heavy
        if additional_green and additional_green > 0:
            clamped = min(additional_green, self.MAX_GREEN_TIME)
            logger.info(f"Emergency Step 10: Additional GREEN {clamped}s for queue clearance")
            # Extend current green (keep same pair)
            await asyncio.sleep(clamped)

        # Safe transition back to normal cycle
        if self.emergency_direction:
            emergency_pair = self._get_pair_for_direction(self.emergency_direction)
            await self._apply_yellow(emergency_pair, "emergency_clearance_complete")
            await asyncio.sleep(self.YELLOW_TIME)

        await self._apply_all_red("post_emergency_clearance")
        await asyncio.sleep(self.ALL_RED_TIME)

        self.emergency_active = False
        self.emergency_direction = None
        self.current_mode = SignalMode.AUTO
        logger.info("Emergency workflow complete — returning to AUTO mode")

    async def manual_command(self, active_pair: frozenset, duration: float, operator_id: str):
        """
        Administrator manual override.
        Safety transitions still enforced — no immediate flips.
        """
        self.current_mode = SignalMode.MANUAL
        validated_pair = self._validate_pair(active_pair)
        validated_duration = self._clamp_duration(duration)

        logger.info(
            "MANUAL OVERRIDE",
            extra={
                "pair": str(validated_pair),
                "duration": validated_duration,
                "operator": operator_id,
            }
        )

        # Safe transition: yellow current, all-red, then new green
        if self.active_pair and self.active_pair != validated_pair:
            await self._apply_yellow(self.active_pair, f"manual_override_by_{operator_id}")
            await asyncio.sleep(self.YELLOW_TIME)
            await self._apply_all_red(f"manual_all_red_{operator_id}")
            await asyncio.sleep(self.ALL_RED_TIME)

        await self._apply_green(validated_pair, validated_duration, f"manual_{operator_id}")

    def resume_auto(self):
        """Return to automatic mode (clears manual/emergency flags)."""
        if not self.emergency_active:
            self.current_mode = SignalMode.AUTO
            logger.info("Resumed AUTO mode")

    def get_current_state(self) -> dict:
        """Return current signal state dict for API/WebSocket."""
        return {
            "mode": self.current_mode.value,
            "emergency_active": self.emergency_active,
            "emergency_direction": self.emergency_direction.value if self.emergency_direction else None,
            "active_pair": [d.value for d in self.active_pair],
            "signals": {
                d.value: {
                    "phase": self.states[d].phase.value,
                    "phase_elapsed": round(self.states[d].phase_elapsed, 1),
                    "wait_elapsed": round(self.states[d].wait_elapsed, 1),
                }
                for d in Direction
            },
        }

    # -------------------------------------------------------------------------
    # Internal control loop
    # -------------------------------------------------------------------------

    async def _control_loop(self):
        """Main control loop — runs continuously while system is active."""
        while self._running:
            try:
                if self.emergency_active:
                    # Emergency handler manages timing — just check safety
                    await asyncio.sleep(0.5)
                    continue

                if self.current_mode == SignalMode.MANUAL:
                    await asyncio.sleep(0.5)
                    continue

                # AUTO mode: advance cycle
                await self._advance_auto_cycle()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Signal control loop error: {e}")
                await asyncio.sleep(1.0)

    async def _advance_auto_cycle(self):
        """Advance the normal auto cycle. Apply starvation prevention."""
        # Determine next pair to get green
        if self.pending_recommendation:
            next_pair = self.pending_recommendation.active_pair
            duration = self.pending_recommendation.green_duration
            reason = self.pending_recommendation.reason
            self.pending_recommendation = None
        else:
            # Default round-robin with starvation check
            next_pair, duration, reason = self._default_next_phase()

        # Starvation prevention: check if any direction has waited too long
        starved = self._check_starvation()
        if starved and starved not in next_pair:
            # Override to serve the starved direction's pair
            next_pair = self._get_pair_for_direction(starved)
            duration = self.MIN_GREEN_TIME
            reason = f"starvation_prevention_{starved.value}"
            logger.warning(f"Starvation prevention: forcing {next_pair}")

        # Safe transition: yellow → all-red → new green
        if self.active_pair and self.active_pair != next_pair:
            await self._apply_yellow(self.active_pair, reason)
            await asyncio.sleep(self.YELLOW_TIME)
            await self._apply_all_red(reason)
            await asyncio.sleep(self.ALL_RED_TIME)

        await self._apply_green(next_pair, duration, reason)
        # Wait for green phase to end
        await asyncio.sleep(duration)

    def _default_next_phase(self) -> tuple[frozenset, float, str]:
        """Default round-robin phase selection."""
        self.cycle_index = (self.cycle_index + 1) % len(SIGNAL_CYCLE)
        pair = SIGNAL_CYCLE[self.cycle_index]
        return pair, self.MIN_GREEN_TIME, "auto_round_robin"

    def _check_starvation(self) -> Optional[Direction]:
        """Return a direction that has waited too long, or None."""
        for d in Direction:
            if self.states[d].phase == SignalPhase.RED:
                if self.states[d].wait_elapsed > self.MAX_WAIT_TIME:
                    logger.warning(f"Starvation detected: {d.value} waited {self.states[d].wait_elapsed:.0f}s")
                    return d
        return None

    # -------------------------------------------------------------------------
    # Phase application helpers
    # -------------------------------------------------------------------------

    async def _apply_green(self, pair: frozenset, duration: float, reason: str):
        """Apply GREEN to compatible pair, RED to others."""
        self._verify_no_conflict(pair)  # Final safety check

        phases = {}
        for d in Direction:
            if d in pair:
                phases[d] = SignalPhase.GREEN
                self.states[d].phase = SignalPhase.GREEN
                self.states[d].phase_start_time = time.time()
                self.states[d].last_green_time = time.time()
            else:
                phases[d] = SignalPhase.RED
                if self.states[d].phase != SignalPhase.RED:
                    self.states[d].phase = SignalPhase.RED
                    self.states[d].phase_start_time = time.time()
                    self.states[d].wait_start_time = time.time()

        self.active_pair = pair
        self._sequence_id += 1

        cmd = ValidatedSignalCommand(
            north=phases[Direction.NORTH],
            south=phases[Direction.SOUTH],
            east=phases[Direction.EAST],
            west=phases[Direction.WEST],
            duration=duration,
            sequence_id=self._sequence_id,
            mode=self.current_mode,
            reason=reason,
        )
        await self._send_command(cmd)
        logger.info(
            "GREEN applied",
            extra={
                "pair": [d.value for d in pair],
                "duration": duration,
                "seq": self._sequence_id,
                "reason": reason,
            }
        )

    async def _apply_yellow(self, pair: frozenset, reason: str):
        """Transition active pair to YELLOW, others stay RED."""
        phases = {}
        for d in Direction:
            if d in pair:
                phases[d] = SignalPhase.YELLOW
                self.states[d].phase = SignalPhase.YELLOW
                self.states[d].phase_start_time = time.time()
            else:
                phases[d] = SignalPhase.RED

        self._sequence_id += 1
        cmd = ValidatedSignalCommand(
            north=phases[Direction.NORTH],
            south=phases[Direction.SOUTH],
            east=phases[Direction.EAST],
            west=phases[Direction.WEST],
            duration=self.YELLOW_TIME,
            sequence_id=self._sequence_id,
            mode=self.current_mode,
            reason=f"yellow_transition_{reason}",
        )
        await self._send_command(cmd)
        logger.debug(f"YELLOW applied to {[d.value for d in pair]}")

    async def _apply_all_red(self, reason: str):
        """Apply RED to all directions (clearance phase)."""
        for d in Direction:
            if self.states[d].phase != SignalPhase.RED:
                self.states[d].phase = SignalPhase.RED
                self.states[d].phase_start_time = time.time()
                self.states[d].wait_start_time = time.time()

        self.active_pair = frozenset()
        self._sequence_id += 1

        cmd = ValidatedSignalCommand(
            north=SignalPhase.RED,
            south=SignalPhase.RED,
            east=SignalPhase.RED,
            west=SignalPhase.RED,
            duration=self.ALL_RED_TIME,
            sequence_id=self._sequence_id,
            mode=self.current_mode,
            reason=f"all_red_{reason}",
        )
        await self._send_command(cmd)
        logger.debug(f"ALL-RED applied: {reason}")

    # -------------------------------------------------------------------------
    # Validation helpers
    # -------------------------------------------------------------------------

    def _validate_pair(self, pair: frozenset) -> frozenset:
        """Ensure pair is a valid compatible pair. Raises if not."""
        if pair not in COMPATIBLE_PAIRS:
            # Try to find the nearest valid pair
            for valid in COMPATIBLE_PAIRS:
                if pair & valid:
                    logger.warning(
                        f"Invalid pair {pair} corrected to {valid}",
                    )
                    return valid
            # Fallback to first pair
            logger.error(f"Completely invalid pair {pair} — using default")
            return COMPATIBLE_PAIRS[0]
        return pair

    def _clamp_duration(self, duration: float) -> float:
        """Clamp duration to [MIN_GREEN_TIME, MAX_GREEN_TIME]."""
        return max(self.MIN_GREEN_TIME, min(duration, self.MAX_GREEN_TIME))

    def _verify_no_conflict(self, pair: frozenset):
        """
        CRITICAL SAFETY CHECK.
        Raises ValueError if pair would create conflicting greens.
        This should NEVER trigger in production — it's a last-resort catch.
        """
        if pair not in COMPATIBLE_PAIRS:
            raise ValueError(
                f"SAFETY VIOLATION: {pair} is not a compatible signal pair! "
                f"Valid pairs: {COMPATIBLE_PAIRS}"
            )

    def _get_pair_for_direction(self, direction: Direction) -> frozenset:
        """Get the compatible pair that includes the given direction."""
        for pair in COMPATIBLE_PAIRS:
            if direction in pair:
                return pair
        raise ValueError(f"No compatible pair found for direction: {direction}")

    # -------------------------------------------------------------------------
    # Command dispatch
    # -------------------------------------------------------------------------

    async def _send_command(self, cmd: ValidatedSignalCommand):
        """Send command to MQTT and broadcast state via WebSocket."""
        if self._command_callback:
            try:
                await self._command_callback(cmd)
            except Exception as e:
                logger.error(f"Failed to send signal command: {e}")

        if self._broadcast_callback:
            try:
                await self._broadcast_callback({
                    "type": "signal_update",
                    "data": {
                        **self.get_current_state(),
                        "command": cmd.as_dict(),
                    }
                })
            except Exception as e:
                logger.error(f"Failed to broadcast signal state: {e}")
