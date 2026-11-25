# ESP32 Traffic Controller — Wiring Diagram

## Overview

12 LEDs total: 4 directions × 3 colors (Red, Yellow, Green)
Each LED uses a 330Ω current-limiting resistor.

---

## Full Wiring Diagram

```
                        ESP32 DEV MODULE
                    ┌─────────────────────┐
                    │                     │
      ┌─── 3.3V ───│ 3V3            GND  │─────┐
      │             │                     │     │
      │    USB ────│ EN              D23  │──┤>├──[330Ω]── WEST YELLOW
      │             │                     │
      │             │ VP/36           D22  │──┤>├──[330Ω]── WEST RED
      │             │ VN/39           TX/1 │
      │             │ D34             RX/3 │
      │             │ D35             D21  │──┤>├──[330Ω]── EAST GREEN
      │             │ D32             D19  │──┤>├──[330Ω]── EAST YELLOW
      │             │ D33             D18  │──┤>├──[330Ω]── EAST RED
      │             │ D25             D5   │──┤>├──[330Ω]── NORTH GREEN
      │             │ ↑               D4   │──┤>├──[330Ω]── NORTH YELLOW
      │          WEST GREEN           D2   │──┤>├──[330Ω]── NORTH RED
      │             │ D26             GND  │
      │             │ D27             D14  │──┤>├──[330Ω]── SOUTH GREEN
      │             │ D14*  (boot)    D12  │──┤>├──[330Ω]── SOUTH RED
      │             │ D12*  (boot)    D13  │──┤>├──[330Ω]── SOUTH YELLOW
      │             │ GND             D15  │
      │             │ 5V              SD2  │
      │             │ D13*            SD3  │
      │             │ SD2             CMD  │
      │             │ SD3             CLK  │
      └─────────────│ CMD             SD0  │
                    │ CLK             SD1  │
                    │ SD0             TX0  │
                    │ SD1             RX0  │
                    └─────────────────────┘
                           │  USB  │
```

> **Note:** D12, D13, D14 have special boot-mode behavior. 
> They are used here for SOUTH LEDs — ensure they are LOW at boot (all LEDs off = LOW = OK).

---

## Per-Direction Wiring Detail

### North Direction (3 LEDs)

```
GPIO 2  ──[330Ω]──┤ RED LED ├── GND
GPIO 4  ──[330Ω]──┤ YEL LED ├── GND
GPIO 5  ──[330Ω]──┤ GRN LED ├── GND
```

### South Direction (3 LEDs)

```
GPIO 12 ──[330Ω]──┤ RED LED ├── GND
GPIO 13 ──[330Ω]──┤ YEL LED ├── GND
GPIO 14 ──[330Ω]──┤ GRN LED ├── GND
```

### East Direction (3 LEDs)

```
GPIO 18 ──[330Ω]──┤ RED LED ├── GND
GPIO 19 ──[330Ω]──┤ YEL LED ├── GND
GPIO 21 ──[330Ω]──┤ GRN LED ├── GND
```

### West Direction (3 LEDs)

```
GPIO 22 ──[330Ω]──┤ RED LED ├── GND
GPIO 23 ──[330Ω]──┤ YEL LED ├── GND
GPIO 25 ──[330Ω]──┤ GRN LED ├── GND
```

---

## Resistor Calculation

**Formula:**  `R = (Vcc - Vf) / If`

| LED Color | Vf (Forward Voltage) | If (Forward Current) | Vcc | R (calc) | R (used) |
|-----------|---------------------|----------------------|-----|----------|----------|
| Red | 1.8V | 10 mA | 3.3V | 150Ω | 330Ω ✓ |
| Yellow | 2.0V | 10 mA | 3.3V | 130Ω | 330Ω ✓ |
| Green | 2.1V | 10 mA | 3.3V | 120Ω | 330Ω ✓ |

> **330Ω is conservative** (reduces current to ~4.5mA for red), resulting in slightly dimmer LEDs
> but much safer for the ESP32's GPIO current limit (12mA max per pin).

**Total current draw** (all 12 LEDs on): 12 × 4.5mA ≈ **54mA** — well within USB power budget.

---

## Breadboard Layout (Top View)

```
         ┌──────────────────────────────────────────────────────────┐
         │  BREADBOARD                                              │
         │                                                          │
  ESP32  │  ┌─────┐  ┌──────────────────────────────────────────┐  │
  ┌────┐ │  │     │  │  NORTH   │  SOUTH   │  EAST    │  WEST   │  │
  │    │ │  │ R   │  │ R  Y  G  │ R  Y  G  │ R  Y  G  │ R  Y  G│  │
  │ G2 │─┼──│ 330 │──│●          │          │          │        │  │
  │ G4 │─┼──│ 330 │──│   ●       │          │          │        │  │
  │ G5 │─┼──│ 330 │──│      ●    │          │          │        │  │
  │G12 │─┼──│ 330 │──│           │●         │          │        │  │
  │G13 │─┼──│ 330 │──│           │   ●      │          │        │  │
  │G14 │─┼──│ 330 │──│           │      ●   │          │        │  │
  │G18 │─┼──│ 330 │──│           │          │●         │        │  │
  │G19 │─┼──│ 330 │──│           │          │   ●      │        │  │
  │G21 │─┼──│ 330 │──│           │          │      ●   │        │  │
  │G22 │─┼──│ 330 │──│           │          │          │●       │  │
  │G23 │─┼──│ 330 │──│           │          │          │   ●    │  │
  │G25 │─┼──│ 330 │──│           │          │          │      ● │  │
  │GND │─┼──────────────────────────────────────────────────────┼──│
  └────┘ │  └─────┘  └──────────────────────────────────────────┘  │
         └──────────────────────────────────────────────────────────┘
                              ● = LED (anode → GPIO, cathode → GND via 330Ω)
```

---

## Power Supply

- **Power from USB**: 5V via USB to ESP32's 5V pin; 3.3V regulated onboard
- **GPIO output**: 3.3V logic, max 12mA per pin, max 40mA total GPIO
- **Recommended**: For production, use external 5V supply with common GND

---

## Notes

1. **Boot-sensitive pins**: GPIO 0, 2, 12, 15 affect boot mode.
   - GPIO 2 (NORTH RED): Must be **LOW at boot** — LED off (not lit) is LOW → safe.
   - GPIO 12 (SOUTH RED): Must be **LOW at boot** → safe.
   - GPIO 15 is not used here.

2. **LED polarity**: The longer leg (anode, +) connects to the GPIO side; the shorter leg (cathode, −) connects to the resistor side going to GND.

3. **For real traffic signals**: Use optocouplers or relay modules driven by these GPIOs to control 12V/24V signal heads. Do NOT connect mains voltage directly to ESP32.
