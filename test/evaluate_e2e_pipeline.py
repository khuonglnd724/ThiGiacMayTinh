"""
evaluate_e2e_pipeline.py - End-to-end pipeline benchmark (Model 1 -> Model 2).

Khác với `test/evaluate_defect_type.py` (crop ROI từ GROUND-TRUTH mask, chỉ đo năng lực
thuần của Model 2), script này chạy toàn bộ pipeline thực tế:

    Model 1 (YOLO segmentation) -> mask dự đoán -> crop ROI -> Model 2 (classifier)

Sau đó tính metrics phân loại end-to-end và so sánh với baseline dùng GT mask để thấy
pipeline (lỗi của bước segmentation) làm giảm bao nhiêu. Đồng thời báo cáo các chỉ số
chẩn đoán pipeline: mask IoU (pred vs GT), tỉ lệ bỏ sót defect (Model 1 không ra mask).

Usage examples
--------------
    # Full pipeline eval + so sánh với baseline GT-mask
    python test/evaluate_e2e_pipeline.py --device cpu

    # Có ràng buộc lớp cha (giống deployment)
    python test/evaluate_e2e_pipeline.py --constrained --device cpu

    # Lưu confusion matrix (end-to-end và baseline)
    python test/evaluate_e2e_pipeline.py --save-cm --device cpu

    # Tuỳ chỉnh ngưỡng Model 1
    python test/evaluate_e2e_pipeline.py --seg-conf 0.3 --seg-iou 0.5 --device cpu
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image

# Make the project root importable so we can reuse AI.defect_type.* modules.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Reuse mask helpers from the Model-1 evaluator (sibling module in same dir).
from evaluate import (  # noqa: E402
    compute_mask_metrics,
    decode_mask_from_result,
    load_ground_truth_mask,
)
# Reuse classifier helpers from the Model-2 evaluator (sibling module in same dir).
from evaluate_defect_type import (  # noqa: E402
    apply_constraint,
    compute_metrics,
    evaluate_test_set,
    load_allowed_map,
)
from AI.defect_type.dataset import (  # noqa: E402
    DefectSample,
    discover_defect_samples,
    split_samples_by_label,
)
from AI.defect_type.model_utils import (  # noqa: E402
    build_image_transform,
    load_checkpoint,
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_SEG_MODEL = (
    "runs/segment/AI/train/runs/ai-segmentation/segmentation/weights/best.pt"
)
DEFAULT_CLS_MODEL = "runs/classify/AI/defect-type/resnet18-global/weights/best.pt"
DEFAULT_PREPROCESS_ROOT = "AI/preprocess/output"
DEFAULT_OUTPUT_DIR = "test/output_e2e_pipeline"
DEFAULT_TAXONOMY = "global"
DEFAULT_BATCH = 32
DEFAULT_SEED = 42
DEFAULT_SEG_CONF = 0.25
DEFAULT_SEG_IOU = 0.45
DEFAULT_SEG_IMGSZ = 640


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------
def resolve_device(device: str) -> torch.device:
    if device != "auto":
        return torch.device(device if device != "cpu" else "cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class PipelineEvalConfig:
    seg_model_path: Path
    cls_model_path: Path
    preprocess_root: Path
    taxonomy: str
    image_size: int
    batch: int
    device: torch.device
    constrained: bool
    output_dir: Path
    seg_conf: float
    seg_iou: float
    seg_imgsz: int
    save_cm: bool
    verbose: bool = True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="End-to-end pipeline evaluation: Model 1 -> ROI -> Model 2."
    )
    p.add_argument("--seg-model", default=DEFAULT_SEG_MODEL, help="YOLO segmentation (Model 1) checkpoint.")
    p.add_argument("--cls-model", default=DEFAULT_CLS_MODEL, help="Defect-type classifier (Model 2) checkpoint.")
    p.add_argument("--preprocess-root", default=DEFAULT_PREPROCESS_ROOT)
    p.add_argument("--taxonomy", choices=["composite", "global"], default=DEFAULT_TAXONOMY)
    p.add_argument("--image-size", type=int, default=None, help="ROI size for Model 2 (defaults to checkpoint).")
    p.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    p.add_argument("--device", default="auto")
    p.add_argument("--constrained", action="store_true", help="Apply parent-class constraint to Model 2.")
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--seg-conf", type=float, default=DEFAULT_SEG_CONF, help="Model 1 confidence threshold.")
    p.add_argument("--seg-iou", type=float, default=DEFAULT_SEG_IOU, help="Model 1 NMS IoU threshold.")
    p.add_argument("--seg-imgsz", type=int, default=DEFAULT_SEG_IMGSZ, help="Model 1 inference size.")
    p.add_argument("--save-cm", action="store_true", help="Save confusion matrix PNGs.")
    return p.parse_args()


def build_config(args: argparse.Namespace) -> PipelineEvalConfig:
    return PipelineEvalConfig(
        seg_model_path=Path(args.seg_model),
        cls_model_path=Path(args.cls_model),
        preprocess_root=Path(args.preprocess_root),
        taxonomy=args.taxonomy,
        image_size=args.image_size,  # resolved to checkpoint's size in main() if None
        batch=args.batch,
        device=resolve_device(args.device),
        constrained=args.constrained,
        output_dir=Path(args.output_dir),
        seg_conf=args.seg_conf,
        seg_iou=args.seg_iou,
        seg_imgsz=args.seg_imgsz,
        save_cm=args.save_cm,
    )


# ---------------------------------------------------------------------------
# End-to-end pipeline evaluation
# ---------------------------------------------------------------------------
def evaluate_pipeline(
    seg_model: Any,
    cls_model: Any,
    cls_metadata: Any,
    test_samples: list[DefectSample],
    cfg: PipelineEvalConfig,
) -> dict[str, Any]:
    label_names: list[str] = list(cls_metadata.label_names)
    label_to_index = {name: i for i, name in enumerate(label_names)}
    missed_label = "<missed/no_mask>"
    extended_labels = label_names + [missed_label]
    missed_index = len(label_names)

    allowed_map = load_allowed_map() if cfg.constrained else {}
    transform = build_image_transform(image_size=cfg.image_size, train=False)
    cls_model.eval()

    predictions: list[int] = []
    targets: list[int] = []
    top2_preds: list[list[int]] = []

    iou_list: list[float] = []
    missed_count = 0

    total = len(test_samples)
    print(f"\nRunning end-to-end pipeline on {total} test samples ...")
    t0 = time.time()

    for idx, sample in enumerate(test_samples):
        if cfg.verbose and (idx + 1) % 50 == 0:
            print(f"  [{idx+1}/{total}]")

        image = Image.open(sample.image_path).convert("RGB")
        gt_mask = load_ground_truth_mask(sample.mask_path, (image.height, image.width))

        # --- Model 1: segmentation -> predicted mask ---
        seg_results = seg_model.predict(
            source=str(sample.image_path),
            imgsz=cfg.seg_imgsz,
            device=str(cfg.device),
            conf=cfg.seg_conf,
            iou=cfg.seg_iou,
            verbose=False,
        )
        pred_mask = None
        if seg_results:
            pred_mask = decode_mask_from_result(seg_results[0], (image.height, image.width))

        # Pipeline diagnostics: mask IoU (pred vs GT)
        if pred_mask is not None and pred_mask.sum() > 0:
            mm = compute_mask_metrics(pred_mask, gt_mask)
            iou_list.append(mm["iou"])
        else:
            # Model 1 detected nothing -> defect missed by segmentation
            missed_count += 1

        # --- Crop ROI from PREDICTED mask, then Model 2 ---
        if pred_mask is not None and pred_mask.sum() > 0:
            mask_pil = Image.fromarray((pred_mask * 255).astype(np.uint8))
            roi = _crop_roi(image, mask_pil, padding_ratio=0.18)
            tensor = transform(roi).unsqueeze(0).to(cfg.device)
            with torch.no_grad():
                logits = cls_model(tensor)
                probs = torch.softmax(logits, dim=1)[0].detach().cpu().numpy()
            best_idx, _, _ = apply_constraint(probs, label_names, sample.class_name, allowed_map)
            values, indices = torch.tensor(probs).topk(k=min(2, len(label_names)))
            top2_preds.append(indices.tolist())
        else:
            # No ROI -> classification impossible -> treat as "missed" class
            best_idx = missed_index
            top2_preds.append([missed_index])

        predictions.append(best_idx)
        targets.append(label_to_index[sample.label])

    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s ({total / elapsed:.1f} img/s)")

    metrics = compute_metrics(predictions, targets, extended_labels, top2_preds)
    mean_iou = float(np.mean(iou_list)) if iou_list else 0.0
    metrics["pipeline_diagnostics"] = {
        "mean_mask_iou_pred_vs_gt": round(mean_iou, 4),
        "mask_iou_samples": len(iou_list),
        "missed_by_segmentation": missed_count,
        "missed_rate": round(missed_count / total, 4) if total else 0.0,
    }
    return metrics


def _crop_roi(image: Image.Image, mask_pil: Image.Image, padding_ratio: float = 0.18) -> Image.Image:
    """Crop ROI around the predicted mask, mirroring dataset.crop_roi_with_mask."""
    from AI.defect_type.dataset import crop_roi_with_mask

    return crop_roi_with_mask(image, mask_pil, padding_ratio=padding_ratio)


# ---------------------------------------------------------------------------
# Confusion matrix plot
# ---------------------------------------------------------------------------
def plot_confusion_matrix(cm: np.ndarray, labels: list[str], save_path: Path, normalize: bool = True) -> None:
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

    plt.figure(figsize=(max(10, len(labels) * 0.5), max(8, len(labels) * 0.5)))
    sns.heatmap(cm, annot=True, fmt=".2f" if normalize else "d", xticklabels=labels, yticklabels=labels, cmap="Blues", cbar=False)
    plt.xlabel("Predicted")
    plt.ylabel("Ground Truth")
    plt.title("Normalized Confusion Matrix" if normalize else "Confusion Matrix")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"  Confusion matrix -> {save_path}")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def save_reports(
    pipeline_metrics: dict[str, Any],
    baseline_metrics: dict[str, Any],
    cfg: PipelineEvalConfig,
    cls_metadata: Any,
) -> None:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "config": {
            "seg_model_path": str(cfg.seg_model_path.resolve()),
            "cls_model_path": str(cfg.cls_model_path.resolve()),
            "preprocess_root": str(cfg.preprocess_root.resolve()),
            "taxonomy": cls_metadata.taxonomy,
            "architecture": cls_metadata.architecture,
            "image_size": cfg.image_size,
            "seg_conf": cfg.seg_conf,
            "seg_iou": cfg.seg_iou,
            "seg_imgsz": cfg.seg_imgsz,
            "device": str(cfg.device),
            "constrained": cfg.constrained,
        },
        "end_to_end": pipeline_metrics,
        "baseline_gt_mask": {k: v for k, v in baseline_metrics.items() if k != "confusion_matrix"},
        "drop_vs_baseline": {
            "accuracy": round(pipeline_metrics["accuracy"] - baseline_metrics["accuracy"], 4),
            "top2_accuracy": round(pipeline_metrics["top2_accuracy"] - baseline_metrics["top2_accuracy"], 4),
            "macro_f1": round(pipeline_metrics["macro_f1"] - baseline_metrics["macro_f1"], 4),
        },
    }

    json_path = cfg.output_dir / "pipeline_evaluation_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  Pipeline report -> {json_path}")

    # Per-class CSV (end-to-end)
    per_class = pipeline_metrics["per_class"]
    if per_class:
        csv_path = cfg.output_dir / "pipeline_per_class_metrics.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(per_class[0].keys()))
            writer.writeheader()
            writer.writerows(per_class)
        print(f"  Per-class CSV   -> {csv_path}")

    if cfg.save_cm:
        plot_confusion_matrix(
            np.asarray(pipeline_metrics["confusion_matrix"], dtype=np.float32),
            cls_metadata.label_names + ["<missed/no_mask>"],
            cfg.output_dir / "pipeline_confusion_matrix.png",
        )
        plot_confusion_matrix(
            np.asarray(baseline_metrics["confusion_matrix"], dtype=np.float32),
            cls_metadata.label_names,
            cfg.output_dir / "baseline_confusion_matrix.png",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    cfg = build_config(parse_args())

    print(f"{'='*60}")
    print("END-TO-END PIPELINE Evaluation")
    print(f"{'='*60}")
    print(f"Seg model : {cfg.seg_model_path}")
    print(f"Cls model : {cfg.cls_model_path}")
    print(f"Preprocess: {cfg.preprocess_root}")
    print(f"Device    : {cfg.device}")
    print(f"Constrained: {cfg.constrained}")

    if not cfg.seg_model_path.exists():
        print(f"Segmentation model not found: {cfg.seg_model_path}")
        return 1
    if not cfg.cls_model_path.exists():
        print(f"Classifier model not found: {cfg.cls_model_path}")
        return 1

    # --- Load Model 1 ---
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics is not installed. Install it with: pip install ultralytics")
        return 1
    seg_model = YOLO(str(cfg.seg_model_path))

    # --- Load Model 2 ---
    try:
        cls_model, cls_metadata = load_checkpoint(cfg.cls_model_path, device=cfg.device)
    except Exception as exc:
        print(f"Failed to load classifier checkpoint: {exc}")
        return 1

    taxonomy = cls_metadata.taxonomy
    if cfg.image_size is None:
        cfg.image_size = cls_metadata.image_size
    print(f"\nLoaded classifier: arch={cls_metadata.architecture} taxonomy={taxonomy} "
          f"num_classes={len(cls_metadata.label_names)} image_size={cfg.image_size}")

    # --- Discover test samples (use classifier taxonomy for GT labels) ---
    all_samples = discover_defect_samples(cfg.preprocess_root, taxonomy=taxonomy, split=None)
    if not all_samples:
        print(f"No defect samples found under {cfg.preprocess_root}. Run preprocessing first.")
        return 1
    test_samples = split_samples_by_label(all_samples, seed=DEFAULT_SEED).test
    print(f"\nTest samples: {len(test_samples)} (of {len(all_samples)} total defect samples)")
    if not test_samples:
        print("No test samples available.")
        return 1

    # --- Baseline: Model 2 on GT-mask crops (isolate classifier ability) ---
    print("\n[Baseline] Evaluating Model 2 on GROUND-TRUTH mask crops ...")
    baseline_metrics = evaluate_test_set(cls_model, cls_metadata, test_samples, _to_cls_config(cfg))

    # --- End-to-end pipeline: Model 1 -> ROI -> Model 2 ---
    pipeline_metrics = evaluate_pipeline(seg_model, cls_model, cls_metadata, test_samples, cfg)

    save_reports(pipeline_metrics, baseline_metrics, cfg, cls_metadata)

    # --- Summary ---
    print(f"\n{'='*60}")
    print("SUMMARY (end-to-end vs GT-mask baseline)")
    print(f"{'='*60}")
    diag = pipeline_metrics["pipeline_diagnostics"]
    print(f"  Pipeline mean mask IoU (pred vs GT): {diag['mean_mask_iou_pred_vs_gt']:.4f} "
          f"(over {diag['mask_iou_samples']} samples with a predicted mask)")
    print(f"  Missed by segmentation (no mask)    : {diag['missed_by_segmentation']} "
          f"({diag['missed_rate']*100:.1f}%)")
    print(f"\n  {'Metric':<16} {'End-to-end':>14} {'Baseline':>14} {'Drop':>10}")
    print("-" * 56)
    for key in ("accuracy", "top2_accuracy", "macro_f1", "macro_precision", "macro_recall"):
        e = pipeline_metrics[key]
        b = baseline_metrics[key]
        print(f"  {key:<16} {e:>14.4f} {b:>14.4f} {e-b:>+10.4f}")
    print(f"\nAll results saved to: {cfg.output_dir.resolve()}")
    return 0


def _to_cls_config(cfg: PipelineEvalConfig):
    """Build an EvalConfig-like object for evaluate_test_set (only fields used)."""
    from evaluate_defect_type import EvalConfig

    return EvalConfig(
        model_path=cfg.cls_model_path,
        preprocess_root=cfg.preprocess_root,
        taxonomy=cfg.taxonomy,
        image_size=cfg.image_size,
        batch=cfg.batch,
        device=cfg.device,
        constrained=cfg.constrained,
        output_dir=cfg.output_dir,
        single_image=None,
        class_name=None,
        save_cm=False,
        compare_runs=False,
    )


if __name__ == "__main__":
    sys.exit(main())