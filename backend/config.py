import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"
RESULTS_DIR = STATIC_DIR / "results"

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_PATH = BASE_DIR / "inspection.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

# AI Models Paths
WORKSPACE_ROOT = BASE_DIR.parent
YOLO_MODEL_PATH = WORKSPACE_ROOT / "runs" / "segment" / "AI" / "train" / "runs" / "ai-segmentation" / "segmentation-yolo11n-27-6-23h" / "weights" / "best.pt"
FALLBACK_YOLO_PATH = WORKSPACE_ROOT / "yolo11n-seg.pt"

def get_yolo_path() -> str:
    """Returns the absolute path to the best trained YOLO weights or fallback."""
    if YOLO_MODEL_PATH.exists():
        return str(YOLO_MODEL_PATH.resolve())
    if FALLBACK_YOLO_PATH.exists():
        return str(FALLBACK_YOLO_PATH.resolve())
    # If not found, return pretrained string for online download
    return "yolo11n-seg.pt"
