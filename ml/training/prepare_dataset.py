"""
ml/training/prepare_dataset.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Creates YOLO dataset directory layout, converts COCO/custom annotations to YOLO
labels for the 7 required vehicle classes, and builds 70/20/10 train/val/test splits.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path
from typing import Dict, List

import yaml

# Required classes (bicycles, cycle rickshaws, and police priority are intentionally excluded)
CLASSES = {
    0: "car",
    1: "motorcycle",
    2: "bus",
    3: "truck",
    4: "auto_rickshaw",
    5: "ambulance",
    6: "fire_brigade",
}

COCO_TO_TARGET = {
    "car": 0,
    "motorcycle": 1,
    "bus": 2,
    "truck": 3,
}


def create_dataset_structure(root: Path) -> None:
    for split in ("train", "val", "test"):
        (root / "images" / split).mkdir(parents=True, exist_ok=True)
        (root / "labels" / split).mkdir(parents=True, exist_ok=True)
    (root / "raw_custom").mkdir(parents=True, exist_ok=True)

    data_yaml = {
        "path": str(root.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": len(CLASSES),
        "names": CLASSES,
    }
    with open(root / "data.yaml", "w") as fh:
        yaml.safe_dump(data_yaml, fh, sort_keys=False)
    print(f"[prepare_dataset] Dataset structure initialized at {root}")


def convert_coco_subset(coco_json: Path, images_dir: Path, out_root: Path) -> int:
    """Convert COCO JSON annotations (car/motorcycle/bus/truck) to YOLO txt labels."""
    with open(coco_json, "r") as fh:
        coco = json.load(fh)

    cat_map: Dict[int, int] = {}
    for cat in coco.get("categories", []):
        name = cat["name"].lower()
        if name in COCO_TO_TARGET:
            cat_map[cat["id"]] = COCO_TO_TARGET[name]

    img_meta = {img["id"]: img for img in coco.get("images", [])}
    anns_by_img: Dict[int, List[str]] = {}

    for ann in coco.get("annotations", []):
        if ann["category_id"] not in cat_map:
            continue
        img = img_meta.get(ann["image_id"])
        if not img:
            continue
        w, h = img["width"], img["height"]
        x, y, bw, bh = ann["bbox"]
        xc = (x + bw / 2.0) / w
        yc = (y + bh / 2.0) / h
        nw = bw / w
        nh = bh / h
        cls_id = cat_map[ann["category_id"]]
        anns_by_img.setdefault(ann["image_id"], []).append(f"{cls_id} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}")

    staged_dir = out_root / "raw_custom"
    converted = 0
    for img_id, lines in anns_by_img.items():
        img = img_meta[img_id]
        src = images_dir / img["file_name"]
        if not src.exists():
            continue
        shutil.copy2(src, staged_dir / src.name)
        label_file = staged_dir / f"{src.stem}.txt"
        label_file.write_text("\n".join(lines), encoding="utf-8")
        converted += 1
    print(f"[prepare_dataset] Converted {converted} COCO images into {staged_dir}")
    return converted


def split_dataset(source_dir: Path, out_root: Path, seed: int = 42) -> Dict[str, int]:
    """Split paired images + .txt labels into 70% train / 20% val / 10% test."""
    image_exts = {".jpg", ".jpeg", ".png", ".bmp"}
    pairs = []
    for p in source_dir.iterdir():
        if p.suffix.lower() in image_exts:
            lbl = p.with_suffix(".txt")
            if lbl.exists():
                pairs.append((p, lbl))

    random.Random(seed).shuffle(pairs)
    n = len(pairs)
    n_train = int(n * 0.70)
    n_val = int(n * 0.20)

    splits = {
        "train": pairs[:n_train],
        "val": pairs[n_train:n_train + n_val],
        "test": pairs[n_train + n_val:],
    }

    counts: Dict[str, int] = {}
    for split, items in splits.items():
        for img_path, lbl_path in items:
            shutil.copy2(img_path, out_root / "images" / split / img_path.name)
            shutil.copy2(lbl_path, out_root / "labels" / split / lbl_path.name)
        counts[split] = len(items)
    print(f"[prepare_dataset] Split counts: {counts}")
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("ml/datasets/traffic_dataset"))
    parser.add_argument("--coco-json", type=Path, default=None)
    parser.add_argument("--coco-images", type=Path, default=None)
    parser.add_argument("--split", action="store_true")
    args = parser.parse_args()

    create_dataset_structure(args.dataset_root)
    if args.coco_json and args.coco_images:
        convert_coco_subset(args.coco_json, args.coco_images, args.dataset_root)
    if args.split:
        split_dataset(args.dataset_root / "raw_custom", args.dataset_root)
