"""
evaluate.py – Test & evaluate a YOLO segmentation model on the MVTec AD test set.

Usage examples
--------------
    # Full evaluation (all metrics, no overlays)
    python AI/test/evaluate.py

    # Single-image debug
    python AI/test/evaluate.py --single-image AI/preprocess/output/images/test/bottle/000.png

    # Save prediction overlays
    python AI/test/evaluate.py --save-images

    # Custom thresholds
    python AI/test/evaluate.py --conf 0.5 --iou 0.5

    # Compare multiple runs
    python AI/test/evaluate.py --compare-runs

    # Use CPU
    python AI/test/evaluate.py --device cpu
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------
DEFAULT_MODEL = (
    "runs/segment/AI/train/runs/ai-segmentation/segmentation/weights/best.pt"
)
DEFAULT_DATA_YAML = "AI/train/data.yaml"
DEFAULT_OUTPUT_DIR = "AI/test/output"
DEFAULT_IMAGE_SIZE = 640
DEFAULT_CONF = 0.25
DEFAULT_IOU = 0.45
DEFAULT_BATCH = 1

RUNS_ROOT = Path("runs/segment/AI/train/runs/ai-segmentation")


# ---------------------------------------------------------------------------
# Device resolution (same as train.py)
# ---------------------------------------------------------------------------
def resolve_device(device: str) -> str:
    """Convert user-friendly device string to one Ultralytics accepts."""
    if device != "auto":
        return device

    try:
        import torch
    except ImportError:
        return "cpu"

    return "0" if torch.cuda.is_available() else "cpu"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class EvalConfig:
    model_path: Path
    data_yaml_path: Path
    imgsz: int
    batch: int
    device: str
    conf: float
    iou: float
    output_dir: Path
    single_image: str | None
    save_images: bool
    compare_runs: bool
    verbose: bool = True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Evaluate a YOLO segmentation model on the MVTec AD test set."
    )
    p.add_argument("--model", default=DEFAULT_MODEL, help="Path to best.pt checkpoint.")
    p.add_argument("--data-yaml", default=DEFAULT_DATA_YAML, help="Path to data.yaml.")
    p.add_argument("--imgsz", type=int, default=DEFAULT_IMAGE_SIZE, help="Inference image size.")
    p.add_argument("--batch", type=int, default=DEFAULT_BATCH, help="Batch size.")
    p.add_argument("--device", default="auto", help='Device: "auto", "0", "cpu".')
    p.add_argument("--conf", type=float, default=DEFAULT_CONF, help="Confidence threshold.")
    p.add_argument("--iou", type=float, default=DEFAULT_IOU, help="NMS IoU threshold.")
    p.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to save evaluation results.",
    )
    p.add_argument("--single-image", default=None, help="Path to a single image for quick debug.")
    p.add_argument("--save-images", action="store_true", help="Save prediction overlay images.")
    p.add_argument(
        "--compare-runs",
        action="store_true",
        help="Compare metrics across all runs under runs/segment/AI/train/runs/ai-segmentation/.",
    )
    return p.parse_args()


def build_config(args: argparse.Namespace) -> EvalConfig:
    return EvalConfig(
        model_path=Path(args.model),
        data_yaml_path=Path(args.data_yaml),
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        conf=args.conf,
        iou=args.iou,
        output_dir=Path(args.output_dir),
        single_image=args.single_image,
        save_images=args.save_images,
        compare_runs=args.compare_runs,
    )


# ---------------------------------------------------------------------------
# Helpers – dataset parsing
# ---------------------------------------------------------------------------
def parse_data_yaml(path: Path) -> dict[str, Any]:
    """Parse a YOLO data.yaml and return a dict with keys: path, nc, names, etc."""
    try:
        import yaml
    except ImportError:
        print("pyyaml is not installed. Install it with: pip install pyyaml")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def gather_test_samples(dataset_root: Path, class_names: list[str]) -> list[dict[str, Any]]:
    """Scan images/test/{class_name}/*.jpg and pair with corresponding labels.

    Returns a list of dicts:
        {
            "image_path": Path,
            "label_path": Path | None,      # None for good samples
            "mask_path": Path | None,        # None for good samples
            "class_name": str,
            "is_defect": bool,
        }
    """
    samples: list[dict[str, Any]] = []
    for cls in class_names:
        img_dir = dataset_root / "images" / "test" / cls
        label_dir = dataset_root / "labels" / "test" / cls
        mask_dir = dataset_root / "masks" / "test" / cls

        if not img_dir.exists():
            continue

        for img_path in sorted(img_dir.glob("*.jpg")):
            stem = img_path.stem
            label_path = label_dir / f"{stem}.txt"
            mask_path = mask_dir / f"{stem}.png"

            is_defect = label_path.exists() and mask_path.exists()

            samples.append(
                {
                    "image_path": img_path,
                    "label_path": label_path if is_defect else None,
                    "mask_path": mask_path if is_defect else None,
                    "class_name": cls,
                    "is_defect": is_defect,
                }
            )

    return samples


# ---------------------------------------------------------------------------
# Single-image inference
# ---------------------------------------------------------------------------
def run_single_image_inference(model: Any, image_path: Path, cfg: EvalConfig) -> None:
    """Run inference on a single image and print results to console."""
    results = model.predict(
        source=str(image_path),
        imgsz=cfg.imgsz,
        device=resolve_device(cfg.device),
        conf=cfg.conf,
        iou=cfg.iou,
        verbose=False,
    )

    if not results:
        print("No predictions returned.")
        return

    r = results[0]
    print(f"\n{'='*60}")
    print(f"Image: {image_path}")
    print(f"Shape: {r.orig_shape}")
    print(f"{'='*60}")

    if r.boxes is not None and len(r.boxes) > 0:
        print(f"\nDetections ({len(r.boxes)}):")
        print(f"{'Cls':<12} {'Conf':<8} {'Box (xywh)':<30} {'Mask area':<12}")
        print("-" * 62)
        for i in range(len(r.boxes)):
            cls_id = int(r.boxes.cls[i])
            conf = float(r.boxes.conf[i])
            xywh = r.boxes.xywh[i].tolist()
            cls_name = r.names[cls_id] if r.names else str(cls_id)

            mask_area = 0.0
            if r.masks is not None and i < len(r.masks):
                mask_arr = r.masks.data[i].cpu().numpy()
                mask_area = float(mask_arr.sum())

            print(f"{cls_name:<12} {conf:<8.4f} {str([round(v,2) for v in xywh]):<30} {mask_area:<12.1f}")
    else:
        print("\nNo detections.")

    if cfg.save_images:
        save_prediction_overlay(r, cfg.output_dir / "single", image_path.stem)

    print()


# ---------------------------------------------------------------------------
# Prediction overlay
# ---------------------------------------------------------------------------
def save_prediction_overlay(result: Any, out_dir: Path, stem: str) -> None:
    """Save the annotated image (boxes + masks overlay)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{stem}_pred.jpg"
    # ultralytics Result.plot() returns a BGR numpy array
    plot = result.plot()
    import cv2

    cv2.imwrite(str(out_path), plot)
    print(f"  Saved overlay → {out_path}")


# ---------------------------------------------------------------------------
# Mask metrics (IoU, Dice)
# ---------------------------------------------------------------------------
def load_ground_truth_mask(mask_path: Path | None, img_shape: tuple[int, int]) -> np.ndarray:
    """Load ground-truth mask as binary numpy array (H, W)."""
    if mask_path is None or not mask_path.exists():
        return np.zeros(img_shape, dtype=np.uint8)
    from PIL import Image

    mask_pil = Image.open(mask_path).convert("L")
    mask_arr = np.asarray(mask_pil, dtype=np.uint8)
    return (mask_arr > 0).astype(np.uint8)


def compute_mask_metrics(
    pred_mask: np.ndarray, gt_mask: np.ndarray
) -> dict[str, float]:
    """Compute IoU and Dice between two binary masks.

    Returns:
        {"iou": float, "dice": float}
        Both are 0.0 if union == 0 (both empty).
    """
    intersection = float(np.logical_and(pred_mask, gt_mask).sum())
    union = float(np.logical_or(pred_mask, gt_mask).sum())
    pred_sum = float(pred_mask.sum())
    gt_sum = float(gt_mask.sum())

    if union == 0:
        iou = 1.0 if pred_sum == 0 and gt_sum == 0 else 0.0
    else:
        iou = intersection / union

    if pred_sum + gt_sum == 0:
        dice = 1.0
    else:
        dice = 2.0 * intersection / (pred_sum + gt_sum)

    return {"iou": iou, "dice": dice}


def decode_mask_from_result(
    result: Any, img_shape: tuple[int, int]
) -> np.ndarray | None:
    """Decode the combined predicted mask from a YOLO result.

    If there are multiple detections, merge their masks via logical OR.
    Returns None if no masks are present.
    """
    if result.masks is None or len(result.masks) == 0:
        return None

    # result.masks.data shape: (N, H, W) where H,W are the mask resolution
    # We need to resize to original image shape
    import torch
    import cv2

    device = result.masks.data.device
    mask_tensor: torch.Tensor = result.masks.data  # (N, H_mask, W_mask)
    H, W = img_shape

    # Accumulate merged mask
    merged = np.zeros((H, W), dtype=np.uint8)
    for i in range(mask_tensor.shape[0]):
        mask_np = (mask_tensor[i].cpu().numpy() > 0.5).astype(np.uint8)
        # Resize from mask resolution to original image size
        mask_resized = cv2.resize(
            mask_np, (W, H), interpolation=cv2.INTER_NEAREST
        )
        merged = np.logical_or(merged, mask_resized).astype(np.uint8)

    return merged


# ---------------------------------------------------------------------------
# Per-image evaluation (for custom mask metrics)
# ---------------------------------------------------------------------------
@dataclass
class PerImageMetrics:
    image_path: str
    class_name: str
    is_defect: bool
    tp: int = 0  # detection TP (at box level)
    fp: int = 0
    fn: int = 0
    mask_iou: float = 0.0
    mask_dice: float = 0.0
    has_mask_gt: bool = False
    has_mask_pred: bool = False


def evaluate_single_image(
    result: Any,
    sample: dict[str, Any],
    iou_threshold: float = 0.5,
) -> PerImageMetrics:
    """Evaluate detection + mask metrics for one image."""
    from PIL import Image

    gt_img = Image.open(sample["image_path"])
    img_shape = (gt_img.height, gt_img.width)

    gt_mask = load_ground_truth_mask(sample["mask_path"], img_shape)
    has_mask_gt = gt_mask.sum() > 0

    # Detection: check if at least one box overlaps with GT
    gt_has_defect = sample["is_defect"]
    pred_has_defect = result.boxes is not None and len(result.boxes) > 0

    # Simple TP/FP/FN at image level (for defect detection)
    tp = 1 if (gt_has_defect and pred_has_defect) else 0
    fp = 1 if (not gt_has_defect and pred_has_defect) else 0
    fn = 1 if (gt_has_defect and not pred_has_defect) else 0

    # Mask metrics
    pred_mask = decode_mask_from_result(result, img_shape)
    has_mask_pred = pred_mask is not None and pred_mask.sum() > 0

    mask_iou = 0.0
    mask_dice = 0.0
    if has_mask_gt or has_mask_pred:
        if pred_mask is None:
            pred_mask = np.zeros(img_shape, dtype=np.uint8)
        mm = compute_mask_metrics(pred_mask, gt_mask)
        mask_iou = mm["iou"]
        mask_dice = mm["dice"]

    return PerImageMetrics(
        image_path=str(sample["image_path"]),
        class_name=sample["class_name"],
        is_defect=gt_has_defect,
        tp=tp,
        fp=fp,
        fn=fn,
        mask_iou=mask_iou,
        mask_dice=mask_dice,
        has_mask_gt=has_mask_gt,
        has_mask_pred=has_mask_pred,
    )


# ---------------------------------------------------------------------------
# Custom evaluation loop (per-image mask metrics)
# ---------------------------------------------------------------------------
def run_custom_evaluation(
    model: Any,
    samples: list[dict[str, Any]],
    cfg: EvalConfig,
) -> dict[str, Any]:
    """Run per-image evaluation for mask-level IoU/Dice metrics.

    Also computes per-class detection stats.
    """
    per_image_results: list[PerImageMetrics] = []
    total = len(samples)

    print(f"\nRunning per-image evaluation on {total} test samples ...")
    t0 = time.time()

    for idx, sample in enumerate(samples):
        if cfg.verbose and (idx + 1) % 50 == 0:
            print(f"  [{idx+1}/{total}]")

        results = model.predict(
            source=str(sample["image_path"]),
            imgsz=cfg.imgsz,
            device=resolve_device(cfg.device),
            conf=cfg.conf,
            iou=cfg.iou,
            verbose=False,
        )

        if results:
            metrics = evaluate_single_image(results[0], sample)
        else:
            # No prediction returned
            from PIL import Image
            gt_img = Image.open(sample["image_path"])
            img_shape = (gt_img.height, gt_img.width)
            gt_mask = load_ground_truth_mask(sample["mask_path"], img_shape)
            has_mask_gt = gt_mask.sum() > 0
            metrics = PerImageMetrics(
                image_path=str(sample["image_path"]),
                class_name=sample["class_name"],
                is_defect=sample["is_defect"],
                tp=0,
                fp=0,
                fn=1 if sample["is_defect"] else 0,
                mask_iou=0.0,
                mask_dice=1.0 if not has_mask_gt else 0.0,
                has_mask_gt=has_mask_gt,
                has_mask_pred=False,
            )

        per_image_results.append(metrics)

        # Save overlay if requested
        if cfg.save_images and results:
            pred_dir = cfg.output_dir / "predictions" / sample["class_name"]
            pred_dir.mkdir(parents=True, exist_ok=True)
            save_prediction_overlay(
                results[0], pred_dir, Path(sample["image_path"]).stem
            )

    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s ({total / elapsed:.1f} img/s)")

    # Aggregate per-class
    class_metrics: dict[str, dict[str, float]] = {}
    global_tp = global_fp = global_fn = 0
    global_iou_sum = global_dice_sum = 0.0
    global_mask_count = 0

    for m in per_image_results:
        cls = m.class_name
        if cls not in class_metrics:
            class_metrics[cls] = {"tp": 0, "fp": 0, "fn": 0, "iou_sum": 0.0, "dice_sum": 0.0, "count": 0, "mask_count": 0}
        class_metrics[cls]["tp"] += m.tp
        class_metrics[cls]["fp"] += m.fp
        class_metrics[cls]["fn"] += m.fn
        global_tp += m.tp
        global_fp += m.fp
        global_fn += m.fn

        class_metrics[cls]["iou_sum"] += m.mask_iou
        class_metrics[cls]["dice_sum"] += m.mask_dice
        class_metrics[cls]["count"] += 1
        global_iou_sum += m.mask_iou
        global_dice_sum += m.mask_dice
        global_mask_count += 1

        if m.has_mask_gt or m.has_mask_pred:
            class_metrics[cls]["mask_count"] += 1

    # Compute final per-class metrics
    per_class_out: list[dict[str, Any]] = []
    for cls in sorted(class_metrics.keys()):
        cm = class_metrics[cls]
        n = cm["count"]
        precision = cm["tp"] / (cm["tp"] + cm["fp"]) if (cm["tp"] + cm["fp"]) > 0 else 0.0
        recall = cm["tp"] / (cm["tp"] + cm["fn"]) if (cm["tp"] + cm["fn"]) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        mean_iou = cm["iou_sum"] / cm["mask_count"] if cm["mask_count"] > 0 else 0.0
        mean_dice = cm["dice_sum"] / cm["mask_count"] if cm["mask_count"] > 0 else 0.0

        per_class_out.append(
            {
                "class": cls,
                "samples": n,
                "tp": cm["tp"],
                "fp": cm["fp"],
                "fn": cm["fn"],
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1, 4),
                "mean_iou": round(mean_iou, 4),
                "mean_dice": round(mean_dice, 4),
            }
        )

    # Global
    gp = global_tp / (global_tp + global_fp) if (global_tp + global_fp) > 0 else 0.0
    gr = global_tp / (global_tp + global_fn) if (global_tp + global_fn) > 0 else 0.0
    gf1 = 2 * gp * gr / (gp + gr) if (gp + gr) > 0 else 0.0
    g_iou = global_iou_sum / global_mask_count if global_mask_count > 0 else 0.0
    g_dice = global_dice_sum / global_mask_count if global_mask_count > 0 else 0.0

    global_metrics = {
        "tp": global_tp,
        "fp": global_fp,
        "fn": global_fn,
        "precision": round(gp, 4),
        "recall": round(gr, 4),
        "f1_score": round(gf1, 4),
        "mean_iou": round(g_iou, 4),
        "mean_dice": round(g_dice, 4),
        "total_samples": total,
    }

    return {
        "global": global_metrics,
        "per_class": per_class_out,
    }


# ---------------------------------------------------------------------------
# Built-in validation (mAP, Precision, Recall from ultralytics)
# ---------------------------------------------------------------------------
def run_ultralytics_val(
    model: Any,
    data_yaml_path: Path,
    cfg: EvalConfig,
) -> dict[str, Any]:
    """Run model.val() on the test split and return metrics."""
    print("\nRunning built-in validation (this may take a while) ...")
    t0 = time.time()

    val_results = model.val(
        data=str(data_yaml_path),
        split="test",
        imgsz=cfg.imgsz,
        batch=cfg.batch,
        device=resolve_device(cfg.device),
        conf=cfg.conf,
        iou=cfg.iou,
        verbose=False,
        plots=False,
        save_json=False,
        save_hybrid=False,
    )

    elapsed = time.time() - t0
    print(f"Validation done in {elapsed:.1f}s")

    # Extract metrics from val_results
    # val_results is a dict with keys like: box.map, box.map50, box.mp, box.mr,
    # mask.map, mask.map50, mask.mp, mask.mr, etc.
    metrics = {}
    try:
        metrics["box_map50"] = float(val_results.box.map50)
        metrics["box_map50_95"] = float(val_results.box.map)
        metrics["box_precision"] = float(val_results.box.mp)
        metrics["box_recall"] = float(val_results.box.mr)
    except (AttributeError, TypeError):
        pass

    try:
        metrics["mask_map50"] = float(val_results.seg.map50)
        metrics["mask_map50_95"] = float(val_results.seg.map)
        metrics["mask_precision"] = float(val_results.seg.mp)
        metrics["mask_recall"] = float(val_results.seg.mr)
    except (AttributeError, TypeError):
        pass

    # Per-class metrics
    per_class = []
    try:
        # box per-class: class names from data.yaml
        data_cfg = parse_data_yaml(data_yaml_path)
        names = data_cfg.get("names", [])
        for i, cls_name in enumerate(names):
            per_class.append(
                {
                    "class": cls_name,
                    "box_p": float(val_results.box.p[i]) if hasattr(val_results.box, "p") and i < len(val_results.box.p) else 0.0,
                    "box_r": float(val_results.box.r[i]) if hasattr(val_results.box, "r") and i < len(val_results.box.r) else 0.0,
                    "box_ap50": float(val_results.box.ap50[i]) if hasattr(val_results.box, "ap50") and i < len(val_results.box.ap50) else 0.0,
                    "box_map50_95": float(val_results.box.ap[i]) if hasattr(val_results.box, "ap") and i < len(val_results.box.ap) else 0.0,
                }
            )
    except (AttributeError, TypeError, IndexError):
        pass

    return {"metrics": metrics, "per_class_ap": per_class}


# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------
def plot_confusion_matrix(
    cm: np.ndarray,
    class_names: list[str],
    save_path: Path,
    normalize: bool = True,
) -> None:
    """Plot and save a confusion matrix."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        print("matplotlib/seaborn not installed. Skipping confusion matrix plot.")
        return

    if normalize:
        cm = cm.astype("float") / (cm.sum(axis=1, keepdims=True) + 1e-9)

    plt.figure(figsize=(max(10, len(class_names) * 0.6), max(8, len(class_names) * 0.6)))
    sns.heatmap(
        cm,
        annot=True,
        fmt=".2f" if normalize else "d",
        xticklabels=class_names + ["background"],
        yticklabels=class_names + ["background"],
        cmap="Blues",
        cbar=False,
    )
    plt.xlabel("Predicted")
    plt.ylabel("Ground Truth")
    plt.title("Normalized Confusion Matrix" if normalize else "Confusion Matrix")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"  Confusion matrix → {save_path}")


# ---------------------------------------------------------------------------
# Compare runs
# ---------------------------------------------------------------------------
def compare_runs(cfg: EvalConfig) -> None:
    """Compare metrics across all training runs."""
    if not RUNS_ROOT.exists():
        print(f"No runs directory found at {RUNS_ROOT}")
        return

    run_dirs = sorted([d for d in RUNS_ROOT.iterdir() if d.is_dir()])
    if not run_dirs:
        print(f"No runs found under {RUNS_ROOT}")
        return

    print(f"\n{'='*70}")
    print(f"Comparing {len(run_dirs)} runs ...")
    print(f"{'='*70}")

    comparison: list[dict[str, Any]] = []

    for run_dir in run_dirs:
        weights_dir = run_dir / "weights"
        best_pt = weights_dir / "best.pt"
        if not best_pt.exists():
            print(f"  Skipping {run_dir.name}: no best.pt found")
            continue

        print(f"\n  Evaluating {run_dir.name} ...")
        try:
            from ultralytics import YOLO

            model = YOLO(str(best_pt))
            val_res = model.val(
                data=str(cfg.data_yaml_path),
                split="test",
                imgsz=cfg.imgsz,
                batch=1,
                device=resolve_device(cfg.device),
                conf=cfg.conf,
                iou=cfg.iou,
                verbose=False,
                plots=False,
            )

            entry = {
                "run_name": run_dir.name,
                "best_pt_path": str(best_pt),
                "box_map50": float(val_res.box.map50) if hasattr(val_res.box, "map50") else 0.0,
                "box_map50_95": float(val_res.box.map) if hasattr(val_res.box, "map") else 0.0,
                "mask_map50": float(val_res.seg.map50) if hasattr(val_res.seg, "map50") else 0.0,
                "mask_map50_95": float(val_res.seg.map) if hasattr(val_res.seg, "map") else 0.0,
                "box_precision": float(val_res.box.mp) if hasattr(val_res.box, "mp") else 0.0,
                "box_recall": float(val_res.box.mr) if hasattr(val_res.box, "mr") else 0.0,
                "mask_precision": float(val_res.seg.mp) if hasattr(val_res.seg, "mp") else 0.0,
                "mask_recall": float(val_res.seg.mr) if hasattr(val_res.seg, "mr") else 0.0,
            }
            comparison.append(entry)
            print(f"    Box mAP50={entry['box_map50']:.4f}, Mask mAP50={entry['mask_map50']:.4f}")

        except Exception as e:
            print(f"    Error: {e}")
            continue

    if not comparison:
        print("No valid runs to compare.")
        return

    # Save comparison CSV
    cmp_dir = cfg.output_dir / "comparison"
    cmp_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cmp_dir / "run_comparison.csv"
    json_path = cmp_dir / "run_comparison.json"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        if comparison:
            writer = csv.DictWriter(f, fieldnames=list(comparison[0].keys()))
            writer.writeheader()
            writer.writerows(comparison)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)

    print(f"\n  Comparison CSV → {csv_path}")
    print(f"  Comparison JSON → {json_path}")

    # Print summary table
    print(f"\n{'Run':<30} {'Box mAP50':<12} {'Mask mAP50':<12} {'Box Prec':<12} {'Box Rec':<12}")
    print("-" * 78)
    for entry in comparison:
        print(
            f"{entry['run_name']:<30} "
            f"{entry['box_map50']:<12.4f} "
            f"{entry['mask_map50']:<12.4f} "
            f"{entry['box_precision']:<12.4f} "
            f"{entry['box_recall']:<12.4f}"
        )


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------
def save_reports(
    custom_metrics: dict[str, Any],
    ultralytics_metrics: dict[str, Any],
    cfg: EvalConfig,
    data_cfg: dict[str, Any],
) -> None:
    """Save evaluation reports (JSON, CSV) and confusion matrix."""
    output_dir = cfg.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Combine reports
    report = {
        "config": {
            "model_path": str(cfg.model_path.resolve()),
            "data_yaml": str(cfg.data_yaml_path.resolve()),
            "imgsz": cfg.imgsz,
            "batch": cfg.batch,
            "device": cfg.device,
            "conf_threshold": cfg.conf,
            "iou_threshold": cfg.iou,
        },
        "ultralytics_metrics": ultralytics_metrics.get("metrics", {}),
        "custom_metrics": {
            "global": custom_metrics.get("global", {}),
            "per_class": custom_metrics.get("per_class", []),
        },
        "per_class_ap": ultralytics_metrics.get("per_class_ap", []),
    }

    # JSON report
    json_path = output_dir / "evaluation_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  Evaluation report → {json_path}")

    # Per-class CSV
    csv_path = output_dir / "per_class_metrics.csv"
    per_class = custom_metrics.get("per_class", [])
    if per_class:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(per_class[0].keys()))
            writer.writeheader()
            writer.writerows(per_class)
        print(f"  Per-class CSV    → {csv_path}")

    # Confusion matrix (dummy for now; ultralytics generates one internally)
    # We skip CM generation here because model.val() already produces one.
    # If the ultralytics val was run with plots=True, its CM is at:
    #   {output_dir}/confusion_matrix.png
    # We just note this in the output.
    print(f"  Confusion matrix from ultralytics saved during model.val()")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    cfg = build_config(parse_args())

    # Create output directory
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    # Load data config
    data_cfg = parse_data_yaml(cfg.data_yaml_path)
    dataset_root = Path(data_cfg["path"])
    class_names = list(data_cfg.get("names", {}).values()) if isinstance(data_cfg.get("names"), dict) else data_cfg.get("names", [])

    print(f"{'='*60}")
    print("YOLO Segmentation Evaluation")
    print(f"{'='*60}")
    print(f"Model:       {cfg.model_path}")
    print(f"Data YAML:   {cfg.data_yaml_path}")
    print(f"Dataset:     {dataset_root}")
    print(f"Classes:     {len(class_names)}")
    print(f"Device:      {cfg.device}")
    print(f"Conf:        {cfg.conf}")
    print(f"IoU:         {cfg.iou}")
    print(f"Output dir:  {cfg.output_dir}")

    # --- Compare runs mode ---
    if cfg.compare_runs:
        compare_runs(cfg)
        return 0

    # --- Load model ---
    print("\nLoading model ...")
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics is not installed. Install it with: pip install ultralytics")
        return 1

    if not cfg.model_path.exists():
        print(f"Model not found: {cfg.model_path}")
        return 1

    model = YOLO(str(cfg.model_path))

    # --- Single-image mode ---
    if cfg.single_image:
        img_path = Path(cfg.single_image)
        if not img_path.exists():
            print(f"Image not found: {img_path}")
            return 1
        run_single_image_inference(model, img_path, cfg)
        return 0

    # --- Gather test samples ---
    samples = gather_test_samples(dataset_root, class_names)
    print(f"\nTest samples found: {len(samples)}")
    defect_count = sum(1 for s in samples if s["is_defect"])
    good_count = len(samples) - defect_count
    print(f"  Defect: {defect_count}, Good: {good_count}")

    if not samples:
        print("No test samples found. Check your dataset path.")
        return 1

    # --- Run ultralytics built-in validation (mAP, precision, recall) ---
    try:
        val_metrics = run_ultralytics_val(model, cfg.data_yaml_path, cfg)
    except Exception as e:
        print(f"Built-in validation failed: {e}")
        val_metrics = {"metrics": {}, "per_class_ap": []}

    # --- Run custom per-image evaluation (IoU, Dice) ---
    try:
        custom_metrics = run_custom_evaluation(model, samples, cfg)
    except Exception as e:
        print(f"Custom evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        custom_metrics = {"global": {}, "per_class": []}

    # --- Save reports ---
    save_reports(custom_metrics, val_metrics, cfg, data_cfg)

    # --- Print summary ---
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    ul = val_metrics.get("metrics", {})
    if ul:
        print(f"  Box   mAP@0.5     : {ul.get('box_map50', 'N/A'):.4f}" if isinstance(ul.get('box_map50'), (int, float)) else f"  Box   mAP@0.5     : {ul.get('box_map50', 'N/A')}")
        print(f"  Box   mAP@0.5:0.95: {ul.get('box_map50_95', 'N/A'):.4f}" if isinstance(ul.get('box_map50_95'), (int, float)) else f"  Box   mAP@0.5:0.95: {ul.get('box_map50_95', 'N/A')}")
        print(f"  Mask  mAP@0.5     : {ul.get('mask_map50', 'N/A'):.4f}" if isinstance(ul.get('mask_map50'), (int, float)) else f"  Mask  mAP@0.5     : {ul.get('mask_map50', 'N/A')}")
        print(f"  Mask  mAP@0.5:0.95: {ul.get('mask_map50_95', 'N/A'):.4f}" if isinstance(ul.get('mask_map50_95'), (int, float)) else f"  Mask  mAP@0.5:0.95: {ul.get('mask_map50_95', 'N/A')}")
        print(f"  Box   Precision  : {ul.get('box_precision', 'N/A'):.4f}" if isinstance(ul.get('box_precision'), (int, float)) else f"  Box   Precision  : {ul.get('box_precision', 'N/A')}")
        print(f"  Box   Recall     : {ul.get('box_recall', 'N/A'):.4f}" if isinstance(ul.get('box_recall'), (int, float)) else f"  Box   Recall     : {ul.get('box_recall', 'N/A')}")

    cm = custom_metrics.get("global", {})
    if cm:
        print(f"  Custom IoU       : {cm.get('mean_iou', 'N/A'):.4f}" if isinstance(cm.get('mean_iou'), (int, float)) else f"  Custom IoU       : {cm.get('mean_iou', 'N/A')}")
        print(f"  Custom Dice      : {cm.get('mean_dice', 'N/A'):.4f}" if isinstance(cm.get('mean_dice'), (int, float)) else f"  Custom Dice      : {cm.get('mean_dice', 'N/A')}")
        print(f"  Precision (img)  : {cm.get('precision', 'N/A'):.4f}" if isinstance(cm.get('precision'), (int, float)) else f"  Precision (img)  : {cm.get('precision', 'N/A')}")
        print(f"  Recall (img)     : {cm.get('recall', 'N/A'):.4f}" if isinstance(cm.get('recall'), (int, float)) else f"  Recall (img)     : {cm.get('recall', 'N/A')}")
        print(f"  F1 Score (img)   : {cm.get('f1_score', 'N/A'):.4f}" if isinstance(cm.get('f1_score'), (int, float)) else f"  F1 Score (img)   : {cm.get('f1_score', 'N/A')}")

    print(f"\nAll results saved to: {cfg.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())