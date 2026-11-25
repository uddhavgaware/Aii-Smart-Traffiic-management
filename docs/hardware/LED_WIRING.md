# LED Wiring & Electrical Calculations

See detailed ASCII schematic in [esp32/documentation/WIRING_DIAGRAM.md](../../esp32/documentation/WIRING_DIAGRAM.md).

## Resistor Selection (3.3V ESP32 GPIO)
- ESP32 GPIO HIGH voltage: $V_{OH} = 3.3\text{ V}$
- Standard 5mm LED forward voltage:
  - Red / Yellow: $V_f \approx 2.0\text{ V}$
  - Green: $V_f \approx 2.2\text{ V}$ (some high-brightness green LEDs are ~3.0V)
- Target safe GPIO current: $I_f \approx 4\text{ mA}$ (well below ESP32 max 12–40mA per pin and safe across 4 simultaneously active LEDs):
  $$R = \frac{3.3 - 2.0}{0.004} = 325\,\Omega \rightarrow \mathbf{330\,\Omega}$$
- Connect each GPIO → `330Ω` resistor → LED Anode (+ long leg) → LED Cathode (- flat side) → Common Breadboard `GND` rail → ESP32 `GND`.
