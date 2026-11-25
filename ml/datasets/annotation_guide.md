# Annotation Guide for Traffic Dataset

## General Rules

1. **Annotate every visible vehicle** — even if partially occluded (>30% visible required).
2. Use **tight bounding boxes** — the box should fit the vehicle body, not include shadow or blur.
3. For occluded vehicles, draw the box around the **visible portion only** — do not guess hidden parts.
4. **One label per vehicle** — do not label parts (wheels, windows) separately.
5. Annotate in **YOLO format** (normalized xywh): all coordinates between 0 and 1.
6. Use **LabelImg** (recommended) or **Roboflow** for annotation.

---

## Class-by-Class Guidelines

### Class 0: `car`
- Includes: sedans, hatchbacks, SUVs, MPVs, station wagons, EVs (Nexon EV, Tiago EV, etc.)
- **Do annotate**: Any 4-wheeled personal vehicle that is NOT a truck/bus/auto.
- **Do NOT annotate as car**: Pickup trucks (→ truck), jeeps/vans used commercially (→ truck).
- Occluded: Annotate if you can see at least the front half or rear half clearly.

### Class 1: `motorcycle`
- Includes: motorcycles, scooters (Activa, etc.), mopeds, e-scooters, three-wheelers (thelo) only if 2-wheeled variant
- **Do NOT annotate as motorcycle**: Auto-rickshaws (→ auto_rickshaw), delivery tricycles (→ truck or skip).
- Note: Annotate the rider as part of the motorcycle box (don't separate rider from vehicle).

### Class 2: `bus`
- Includes: city buses (DTC, BMTC), school buses, minibuses (Tempo Traveller), private coaches, Volvo AC buses
- **Do annotate**: Any large passenger vehicle with more than 15 seats.
- **Do NOT annotate as bus**: Auto-rickshaws carrying passengers (→ auto_rickshaw), small vans (→ truck).

### Class 3: `truck`
- Includes: cargo trucks, lorries, pickup trucks, delivery vans, cement mixers, tankers, tippers, container trucks
- **Do annotate**: Any vehicle primarily for cargo/goods transport.
- **Ambiguous cases**: Tempo/loading vehicles (3-wheeled cargo) → annotate as truck if clearly cargo-purpose.

### Class 4: `auto_rickshaw`
- Includes: CNG/electric auto-rickshaws, tuk-tuks, e-rickshaws (3-wheeled)
- **Do annotate**: 3-wheeled passenger/goods vehicles typical in Indian urban context.
- **Do NOT annotate as auto**: Cycle rickshaws (pedal-powered, skip entirely), 4-wheeled taxis (→ car).
- Note: This is the most India-specific class — annotate generously.

### Class 5: `ambulance`
- Includes: Govt ambulances (108, 102), private hospital ambulances, Maruti Omni ambulances, converted vans
- **Important**: Label **ALL** ambulance-type vehicles, even if NOT responding with lights/siren.
  - Emergency *activity* (flashing lights) is detected by Stage 2, not annotation.
- **Visual cues**: "AMBULANCE" text (often mirrored), red/white/yellow livery, medical cross symbol, stretcher equipment visible.
- If unsure whether a vehicle is an ambulance, skip it rather than mislabel.

### Class 6: `fire_brigade`
- Includes: fire engines, water tenders, aerial platforms, fire command vehicles, quick response vehicles (QRV)
- **Visual cues**: Red livery, "FIRE" text, hoses/ladders visible, fire department insignia.
- Rare class — annotate every visible instance carefully.
- **Do NOT annotate**: Police vehicles (skip), water tankers without fire insignia (→ truck).

---

## Handling Difficult Cases

### Heavily Occluded Vehicles
- **>70% occluded**: Skip (do not annotate)
- **30-70% occluded**: Annotate the visible region tightly
- **<30% occluded**: Annotate normally

### Night Images / Low Light
- Use the same class rules
- If you cannot identify the vehicle type with ≥80% confidence, skip
- Motion blur alone is not a reason to skip — if the shape is clear, annotate

### Overlapping Vehicles
- Annotate each vehicle separately even if boxes overlap
- Do NOT merge overlapping vehicles into one box

### Vehicles at Image Edges
- Annotate if >50% of the vehicle is within the image boundary
- The box may extend slightly beyond the image — that is fine in YOLO format (clip to [0, 1])

### Convoy / Parade
- Annotate each vehicle individually
- Emergency vehicles in convoy → still label each as ambulance/fire_brigade

---

## Quality Checklist Before Submitting

- [ ] All visible vehicles (>30% visible) are annotated
- [ ] No duplicate annotations for the same vehicle
- [ ] Boxes are tight (no excessive padding)
- [ ] Class IDs are correct (0-6 only)
- [ ] No labels for pedestrians, cyclists (non-motorized), or animals
- [ ] Label file has same name as image file (only extension differs)
- [ ] Label file is in the correct directory (labels/train, labels/val, labels/test)
- [ ] All coordinates are between 0 and 1

---

## Recommended Tools

| Tool        | Platform | Notes                                         |
|-------------|----------|-----------------------------------------------|
| LabelImg    | Desktop  | Free, open-source, YOLO format native         |
| Roboflow    | Web      | Cloud-based, good for teams, free tier limits |
| CVAT        | Web/Self-hosted | Enterprise-grade, free self-hosted     |
| Label Studio| Web/Self-hosted | Flexible, ML-assisted labeling         |

### LabelImg Quick Start
```bash
pip install labelImg
labelImg images/train labels/train
# In GUI: select YOLO format, set default save dir to labels/train
```
