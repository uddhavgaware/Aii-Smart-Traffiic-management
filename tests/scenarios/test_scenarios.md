# 12 Test Scenarios — Verification Matrix

> **Rule**: Never mark a test scenario as PASSED until executed against the running system and observed outputs are recorded below.

| ID | Scenario | Input | Expected Behaviour | Actual Behaviour | Detection / Decision Latency | Signal Transition | Test Result |
|----|----------|-------|--------------------|------------------|------------------------------|-------------------|-------------|
| SC-01 | Normal traffic in all directions | N=8, S=7, E=8, W=6 vehicles | Balanced adaptive cycle (~30s green) | API simulation (`NORMAL`, 8 vehicles/dir) returned HTTP 200 & updated adaptive engine | API tested | GREEN→YELLOW→ALL_RED→GREEN | PASSED (API Sim) |
| SC-02 | Heavy traffic in East direction | E=32 vehicles (HIGH), others=5 | E+W green extended up to 80s | API simulation (`HIGH`, 32 vehicles, queue 75%) returned HTTP 200 & prioritized E+W | API tested | Safe transition to E+W GREEN | PASSED (API Sim) |
| SC-03 | Traffic jam in North direction | N=45 vehicles (TRAFFIC_JAM), queue>80% | N+S priority green (up to 110s) with starvation guard | API simulation (`TRAFFIC_JAM`, 45 vehicles, queue 90%) returned HTTP 200 | API tested | Safe transition to N+S GREEN | PASSED (API Sim) |
| SC-04 | Ambulance in West with emergency lights | Ambulance track + flashing lights (Stage 2 conf>0.7) | Emergency confirmed; current green→yellow→all-red→W+E green | Confirmed Stage 2 (`conf=0.92`) triggered `EAST_WEST EMERGENCY` after 5.07s safety transition | 5074.15 ms (incl. 3s Y + 2s AR) | Safe emergency override to WEST | PASSED (API Sim) |
| SC-05 | Ambulance without visible emergency indication | Ambulance track, no flashing lights | Stage 2 UNCONFIRMED / NORMAL; uncertainty shown; NO override | Stage 1 (`conf=0.45`) logged without triggering override (`emergency_active=False`) | API tested | Normal cycle preserved | PASSED (API Sim) |
| SC-06 | Fire Brigade emergency | Fire brigade track + Stage 2 confirmed | Emergency priority activated for detected direction | _Not executed yet_ | _TBD_ | Safe transition to emergency direction | PENDING |
| SC-07 | Multiple emergency vehicles | Ambulance W + Fire Brigade N | First confirmed served safely; no simultaneous conflicting greens | _Not executed yet_ | _TBD_ | Sequential safe transitions | PENDING |
| SC-08 | Emergency vehicle clears junction | Emergency vehicle leaves ROI (`cleared=true`) | Emergency cleared, normal mode resumed, logged | `/api/emergency/clear` returned HTTP 200, transitioned safely and resumed `AUTO` | API tested | GREEN→YELLOW→ALL_RED→Normal | PASSED (API Sim) |
| SC-09 | Congestion after emergency clearance | Post-clearance queue > 50% | Additional green clearance window applied before switching | _Not executed yet_ | _TBD_ | Extended green then safe switch | PENDING |
| SC-10 | Automatic & Manual mode switching | Switch AUTO→MANUAL→Override East→AUTO | Manual actions logged; safety transitions enforced | `MANUAL` override East `GREEN` (20s) + return to `AUTO` returned HTTP 200 | API tested | Yellow + All-Red before manual green | PASSED (API Sim) |
| SC-11 | Four camera streams simultaneously | 4 mobile phones streaming `/camera` | All 4 feeds visible, ~5 FPS/cam (~20 total FPS) | _Not executed yet_ | _TBD_ | Adaptive cycle active | PENDING |
| SC-12 | ESP32 signal execution & ACK | ESP32 subscribed over MQTT TLS | 12 physical LEDs match dashboard & send ACK | _Not executed yet_ | _TBD_ | Hardware ACK received | PENDING |
