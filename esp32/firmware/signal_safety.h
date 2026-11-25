/**
 * signal_safety.h - Hardware-level Signal Safety Validation
 *
 * This module enforces traffic signal safety INDEPENDENTLY of the backend.
 * Even if the MQTT command is malformed or the backend has a bug, the firmware
 * will NEVER allow conflicting greens that could cause collisions.
 *
 * Safety rules enforced:
 *   1. No two perpendicular directions can have GREEN simultaneously.
 *   2. Only compatible pairs allowed: (NORTH+SOUTH) or (EAST+WEST).
 *   3. Transitions must follow: GREEN → YELLOW → ALL_RED → GREEN
 *   4. GREEN duration must be within [MIN_GREEN_DURATION, MAX_GREEN_DURATION].
 *   5. At most ONE pair of directions can be GREEN at once.
 */

#ifndef SIGNAL_SAFETY_H
#define SIGNAL_SAFETY_H

#include "config.h"

// ─────────────────────────────────────────────────────────────
// Enumerations
// ─────────────────────────────────────────────────────────────

enum class SignalPhase : uint8_t {
    RED    = 0,
    YELLOW = 1,
    GREEN  = 2,
    UNKNOWN = 255
};

enum class Direction : uint8_t {
    NORTH = 0,
    SOUTH = 1,
    EAST  = 2,
    WEST  = 3
};

// ─────────────────────────────────────────────────────────────
// Data Structures
// ─────────────────────────────────────────────────────────────

struct DirectionState {
    SignalPhase phase;
    uint32_t    duration_ms;   // requested green duration in ms
};

struct SignalCommand {
    uint32_t       sequence_id;
    DirectionState north;
    DirectionState south;
    DirectionState east;
    DirectionState west;
};

struct ValidationResult {
    bool    valid;
    char    reason[128];  // human-readable error if invalid
};

// ─────────────────────────────────────────────────────────────
// Safety Validation Functions
// ─────────────────────────────────────────────────────────────

/**
 * Check if two directions are compatible (can be GREEN simultaneously).
 * Only NORTH+SOUTH or EAST+WEST are allowed concurrent greens.
 */
inline bool areCompatibleDirections(Direction d1, Direction d2) {
    if (d1 == d2) return true;  // same direction, trivially compatible
    if ((d1 == Direction::NORTH && d2 == Direction::SOUTH) ||
        (d1 == Direction::SOUTH && d2 == Direction::NORTH)) return true;
    if ((d1 == Direction::EAST  && d2 == Direction::WEST)  ||
        (d1 == Direction::WEST  && d2 == Direction::EAST))  return true;
    return false;
}

/**
 * Check if a phase transition is valid.
 * Valid transitions:
 *   GREEN  → YELLOW   (normal end of green)
 *   YELLOW → RED      (via ALL_RED intermediate, managed by state machine)
 *   RED    → GREEN    (start of new green phase, after ALL_RED clearance)
 *   RED    → RED      (staying red is fine)
 *   GREEN  → GREEN    (extending current green is fine)
 *
 * INVALID:
 *   GREEN  → RED      (must go through YELLOW)
 *   YELLOW → GREEN    (cannot skip ALL_RED)
 */
inline bool isValidTransition(SignalPhase current, SignalPhase next) {
    if (current == next) return true;  // no change
    switch (current) {
        case SignalPhase::GREEN:
            return (next == SignalPhase::YELLOW);  // must transition through yellow
        case SignalPhase::YELLOW:
            return (next == SignalPhase::RED);     // yellow → red only
        case SignalPhase::RED:
            return (next == SignalPhase::GREEN || next == SignalPhase::RED);
        default:
            return false;
    }
}

/**
 * Validate an incoming signal command for safety.
 * Returns a ValidationResult with valid=true if safe, or valid=false + reason.
 */
inline ValidationResult validateSignalCommand(const SignalCommand& cmd) {
    ValidationResult result;
    result.valid = true;
    result.reason[0] = '\0';

    // Count greens and check for conflicts
    bool northGreen = (cmd.north.phase == SignalPhase::GREEN);
    bool southGreen = (cmd.south.phase == SignalPhase::GREEN);
    bool eastGreen  = (cmd.east.phase  == SignalPhase::GREEN);
    bool westGreen  = (cmd.west.phase  == SignalPhase::GREEN);

    // Rule 1: No conflicting greens (perpendicular directions)
    if (northGreen || southGreen) {
        if (eastGreen || westGreen) {
            result.valid = false;
            snprintf(result.reason, sizeof(result.reason),
                "SAFETY VIOLATION: Conflicting greens! "
                "N/S green with E/W green simultaneously prohibited.");
            return result;
        }
    }

    // Rule 2: Check YELLOW conflicts (yellow in one axis, green in perpendicular)
    bool northYellow = (cmd.north.phase == SignalPhase::YELLOW);
    bool southYellow = (cmd.south.phase == SignalPhase::YELLOW);
    bool eastYellow  = (cmd.east.phase  == SignalPhase::YELLOW);
    bool westYellow  = (cmd.west.phase  == SignalPhase::YELLOW);

    if ((northYellow || southYellow) && (eastGreen || westGreen)) {
        result.valid = false;
        snprintf(result.reason, sizeof(result.reason),
            "SAFETY VIOLATION: N/S yellow with E/W green is unsafe.");
        return result;
    }
    if ((eastYellow || westYellow) && (northGreen || southGreen)) {
        result.valid = false;
        snprintf(result.reason, sizeof(result.reason),
            "SAFETY VIOLATION: E/W yellow with N/S green is unsafe.");
        return result;
    }

    // Rule 3: Validate green durations
    auto checkDuration = [&](const DirectionState& state, const char* dir) -> bool {
        if (state.phase == SignalPhase::GREEN) {
            if (state.duration_ms < MIN_GREEN_DURATION) {
                snprintf(result.reason, sizeof(result.reason),
                    "INVALID: %s green duration %lu ms < minimum %lu ms",
                    dir, (unsigned long)state.duration_ms, (unsigned long)MIN_GREEN_DURATION);
                return false;
            }
            if (state.duration_ms > MAX_GREEN_DURATION) {
                snprintf(result.reason, sizeof(result.reason),
                    "INVALID: %s green duration %lu ms > maximum %lu ms",
                    dir, (unsigned long)state.duration_ms, (unsigned long)MAX_GREEN_DURATION);
                return false;
            }
        }
        return true;
    };

    if (!checkDuration(cmd.north, "NORTH")) { result.valid = false; return result; }
    if (!checkDuration(cmd.south, "SOUTH")) { result.valid = false; return result; }
    if (!checkDuration(cmd.east,  "EAST"))  { result.valid = false; return result; }
    if (!checkDuration(cmd.west,  "WEST"))  { result.valid = false; return result; }

    // Rule 4: At least one direction must be RED (not all green/yellow at once)
    if (northGreen && southGreen && eastGreen && westGreen) {
        result.valid = false;
        snprintf(result.reason, sizeof(result.reason),
            "SAFETY VIOLATION: All directions GREEN simultaneously is not allowed.");
        return result;
    }

    return result;  // valid = true
}

/**
 * Convert phase enum to string for debug/JSON output.
 */
inline const char* phaseToString(SignalPhase phase) {
    switch (phase) {
        case SignalPhase::RED:    return "RED";
        case SignalPhase::YELLOW: return "YELLOW";
        case SignalPhase::GREEN:  return "GREEN";
        default:                  return "UNKNOWN";
    }
}

/**
 * Parse phase string from JSON to enum.
 */
inline SignalPhase stringToPhase(const char* str) {
    if (str == nullptr) return SignalPhase::UNKNOWN;
    if (strcmp(str, "GREEN")  == 0) return SignalPhase::GREEN;
    if (strcmp(str, "YELLOW") == 0) return SignalPhase::YELLOW;
    if (strcmp(str, "RED")    == 0) return SignalPhase::RED;
    return SignalPhase::UNKNOWN;
}

#endif // SIGNAL_SAFETY_H
