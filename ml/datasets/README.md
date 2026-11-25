# Traffic Dataset Documentation

## Directory Structure

```
datasets/
├── README.md                   ← This file
├── data.yaml                   ← YOLO dataset config template
├── annotation_guide.md         ← Annotation guidelines
└── traffic_dataset/
    ├── data.yaml               ← Active dataset config (copy & edit from template)
    ├── images/
    │   ├── train/              ← Training images (70%)
    │   ├── val/                ← Validation images (20%)
    │   └── test/               ← Test images (10%)
    └── labels/
        ├── train/              ← YOLO labels for training images
        ├── val/                ← YOLO labels for validation images
        └── test/               ← YOLO labels for test images
```

---

## Annotation Format (YOLO Format)

Each image has a corresponding `.txt` label file with the same base name.

Each line in the label file represents one bounding box:
```
<class_id> <x_center> <y_center> <width> <height>
```

All values are **normalized** to [0, 1] relative to image dimensions.

### Example
```
0 0.512 0.432 0.124 0.198
5 0.231 0.611 0.085 0.141
```

This represents:
- A `car` (class 0) centered at (51.2%, 43.2%) with width 12.4% and height 19.8%
- An `ambulance` (class 5) centered at (23.1%, 61.1%) with width 8.5% and height 14.1%

---

## Class Mapping

| Class ID | Class Name     | Category  | Notes                                 |
|----------|---------------|-----------|---------------------------------------|
| 0        | car           | Normal    | Sedans, hatchbacks, SUVs, EVs         |
| 1        | motorcycle    | Normal    | Bikes, scooters, mopeds               |
| 2        | bus           | Normal    | City buses, school buses, minibuses   |
| 3        | truck         | Normal    | Cargo trucks, lorries, pickups        |
| 4        | auto_rickshaw | Normal    | Auto-rickshaws, tuk-tuks (India-specific) |
| 5        | ambulance     | Emergency | All types including private ambulances|
| 6        | fire_brigade  | Emergency | Fire engines, water tenders           |

> **Note on emergency vehicles**: Labeling something as `ambulance` or `fire_brigade` only identifies the *vehicle type*. Whether it is **actively responding** (lights on, siren) is determined by Stage 2 emergency detection, not by class alone.

---

## Dataset Sources

| Source                    | License         | Vehicle Types Covered       | Notes                            |
|---------------------------|-----------------|-----------------------------|----------------------------------|
| COCO 2017 (vehicles only) | CC BY 4.0       | car, bus, truck, motorcycle | Subset filtered for vehicles     |
| OpenImages v7 (vehicles)  | CC BY 4.0       | car, bus, truck             | High diversity, good for variety |
| Indian Driving Dataset    | Research only   | All classes incl. auto      | Best source for Indian traffic   |
| UA-DETRAC                 | Free research   | car, bus, truck             | Highway/urban surveillance cams  |
| Custom collected          | Proprietary     | All 7 classes               | From your own deployed cameras   |

### How to Cite
When using COCO:
```
@article{lin2014microsoft,
  title={Microsoft coco: Common objects in context},
  author={Lin, Tsung-Yi et al.}
}
```

---

## Adding Data from Mobile Cameras

1. **Capture requirements**:
   - Minimum resolution: 720p (1280×720)
   - Frame rate: ≥10 FPS preferred
   - Mount the phone in a fixed position (tripod/mount)
   - Avoid moving the camera during capture

2. **Extract frames from video**:
   ```bash
   # Extract 1 frame per second from a video
   ffmpeg -i your_video.mp4 -vf fps=1 output_frames/frame_%04d.jpg
   ```

3. **Annotate using LabelImg or Roboflow**:
   - Install LabelImg: `pip install labelImg`
   - Set format to YOLO before annotating
   - Save `.txt` labels alongside images
   - See `annotation_guide.md` for detailed guidelines

4. **Place files in dataset directory**:
   ```
   datasets/traffic_dataset/images/train/your_frame_0001.jpg
   datasets/traffic_dataset/labels/train/your_frame_0001.txt
   ```

5. **Re-run split script** to redistribute if needed:
   ```bash
   python scripts/prepare_dataset.py --resplit
   ```

---

## Train / Val / Test Splits

| Split | Ratio | Purpose                                        |
|-------|-------|------------------------------------------------|
| Train | 70%   | Model learning                                 |
| Val   | 20%   | Hyperparameter tuning, early stopping          |
| Test  | 10%   | Final unbiased evaluation (never used in training) |

### Split Strategy
- Splits are done **per scene** (not per frame), so images from the same video clip don't appear across splits (avoids data leakage).
- Emergency vehicle examples are **stratified** across all splits to prevent class imbalance in validation/test.

---

## Recommended Dataset Size

| Stage          | Min Images | Recommended |
|---------------|-----------|-------------|
| Initial test  | 500       | 1,000       |
| First training| 2,000     | 5,000       |
| Production    | 10,000    | 20,000+     |
| Per rare class| 200+      | 500+        |

> Emergency vehicles (ambulance, fire_brigade) are rare — actively collect and augment these images.
