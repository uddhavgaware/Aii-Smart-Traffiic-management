# Model Registry & Versioning

- Place trained YOLOv8 checkpoints under `ml/models/checkpoints/`.
- Active inference weights path is configured in `ml/config/model_config.yaml` (`model.weights: models/checkpoints/best.pt`).
- **Truthfulness Policy**: If `best.pt` does not exist yet, `TrafficDetectionModel` falls back to `yolov8n.pt` and explicitly exposes `model_trained=False` (`not_trained_flag=True`). Never claim custom accuracy metrics prior to running `ml/training/train.py` and `ml/evaluation/evaluate.py`.
