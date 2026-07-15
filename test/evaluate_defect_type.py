"""
evaluate_defect_type.py - Benchmark / evaluate the Model 2 defect-type classifier.

Model 2 is a second-stage classifier (ResNet18 / MobileNetV3 / EfficientNet) that
predicts the *type* of defect from the ROI cropped around a segmentation mask.
This script is the counterpart of `test/evaluate.py` (which benchmarks the YOLO
segmentation Model 1).

Usage examples
--------------
    # Full evaluation of the default resnet18-global classifier (raw, no constraint)
    python test/evaluate_defect_type.py

    # Evaluate with the parent-class constraint (mirrors DefectTypeService)
    python test/evaluate_defect_type.py --constrained

    # Custom checkpoint / taxonomy
    python test/evaluate_defect_type.py --model runs/classify/AI/defect-type/mobilenet_v3_small-global/weights/best.pt

    # Save confusion matrix image
    python test/evaluate_defect_type.py --save-cm

    # Compare multiple trained runs
    python test/evaluate_defect_type.py --compare-runs

    # Single image debug
    python test/evaluate_defect_type.py --single-image path/to/roi.jpg --class-name bottle

    # Force CPU
    python test/evaluate_defect_type.py --device cpu
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

# Make the project root importable so we can reuse AI.defect_type.* modules.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AI.defect_type.dataset import (  # noqa: E402
    DefectSample,
    collect_label_names,
    crop_roi_with_mask,
    discover_defect_samples,
    split_samples_by_label,
)
from AI.defect_type.model_utils import (  # noqa: E402
    build_image_transform,
    load_checkpoint,
    make_label_display,
    top_k_predictions,
)

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "runs/classify/AI/defect-type/resnet18-global/weights/best.pt"
DEFAULT_PREPROCESS_ROOT = "AI/preprocess/output"
DEFAULT_OUTPUT_DIR = "test/output_defect_type"
DEFAULT_TAXONOMY = "global"
DEFAULT_IMAGE_SIZE = 224
DEFAULT_BATCH = 32
DEFAULT_SEED = 42

RUNS_ROOT = Path("runs/classify/AI/defect-type")
ALLOWED_MAP_PATH = PROJECT_ROOT / "AI" / "defect_type" / "class_defect_allowed.json"


# ---------------------------------------------------------------------------
# Device resolution
# ---------------------------------------------------------------------------
def resolve_device(device: str) -> torch.device:
    if device != "auto":
        return torch.device(device if device != "cpu" else "cpu")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class EvalConfig:
    model_path: Path
    preprocess_root: Path
    taxonomy: str
    image_size: int
    batch: int
    device: torch.device
    constrained: bool
    output_dir: Path
    single_image: str | None
    class_name: str | None
    save_cm: bool
    compare_runs: bool
    verbose: bool = True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Evaluate the Model 2 defect-type classifier on its test split."
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Path to the classifier checkpoint (best.pt).",
    )
    p.add_argument(
        "--preprocess-root",
        default=DEFAULT_PREPROCESS_ROOT,
        help="Preprocessing output root containing images/ and masks/.",
    )
    p.add_argument(
        "--taxonomy",
        choices=["composite", "global"],
        default=DEFAULT_TAXONOMY,
        help="Label strategy used when discovering ground-truth samples.",
    )
    p.add_argument(
        "--image-size",
        type=int,
        default=None,
        help="ROI size fed to the model (defaults to checkpoint's image_size).",
    )
    p.add_argument("--batch", type=int, default=DEFAULT_BATCH, help="Batch size.")
    p.add_argument(
        "--device",
        default="auto",
        help='Device: "auto", "cpu", "cuda", or a CUDA index.',
    )
    p.add_argument(
        "--constrained",
        action="store_true",
        help="Apply the parent-class allowed-list constraint (like DefectTypeService).",
    )
    p.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to save evaluation reports.",
    )
    p.add_argument(
        "--single-image",
        default=None,
        help="Path to a single image for quick debug (uses whole image as ROI).",
    )
    p.add_argument(
        "--class-name",
        default=None,
        help="Product class name used for constraint / single-image debug.",
    )
    p.add_argument(
        "--save-cm",
        action="store_true",
        help="Save the confusion matrix as a PNG image.",
    )
    p.add_argument(
        "--compare-runs",
        action="store_true",
        help="Compare metrics across all runs under runs/classify/AI/defect-type/.",
    )
    return p.parse_args()


def build_config(args: argparse.Namespace) -> EvalConfig:
    return EvalConfig(
        model_path=Path(args.model),
        preprocess_root=Path(args.preprocess_root),
        taxonomy=args.taxonomy,
        image_size=args.image_size if args.image_size else DEFAULT_IMAGE_SIZE,
        batch=args.batch,
        device=resolve_device(args.device),
        constrained=args.constrained,
        output_dir=Path(args.output_dir),
        single_image=args.single_image,
        class_name=args.class_name,
        save_cm=args.save_cm,
        compare_runs=args.compare_runs,
    )


# ---------------------------------------------------------------------------
# Constraint helper (mirrors DefectTypeService)
# ---------------------------------------------------------------------------
def load_allowed_map() -> dict[str, list[str]]:
    if ALLOWED_MAP_PATH.exists():
        try:
            with open(ALLOWED_MAP_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Failed to load class->defect allowed map: {exc}")
    return {}


def apply_constraint(
    probs: np.ndarray,
    label_names: list[str],
    class_name: str | None,
    allowed_map: dict[str, list[str]],
) -> tuple[int, float, bool]:
    """Return (best_idx, confidence, constrained) after optionally constraining.

    Mirrors the logic in backend/services/defect_type_service.py.
    """
    if not class_name or not allowed_map:
        idx = int(np.argmax(probs))
        return idx, float(probs[idx]), False

    allowed_set = set(allowed_map.get(class_name.lower(), []))
    if not allowed_set:
        idx = int(np.argmax(probs))
        return idx, float(probs[idx]), False

    candidate_indices = [i for i, n in enumerate(label_names) if n in allowed_set]
    if not candidate_indices:
        idx = int(np.argmax(probs))
        return idx, float(probs[idx]), False

    best_idx = max(candidate_indices, key=lambda i: probs[i])
    return best_idx, float(probs[best_idx]), True


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def compute_metrics(
    predictions: list[int],
    targets: list[int],
    label_names: list[str],
    top2_preds: list[list[int]] | None = None,
) -> dict[str, Any]:
    num_classes = len(label_names)
    total = len(targets)
    confusion = np.zeros((num_classes, num_classes), dtype=np.int64)

    for target, pred in zip(targets, predictions):
        confusion[target, pred] += 1

    correct = int(np.trace(confusion))
    top2_correct = 0
    if top2_preds is not None:
        for target, top_indices in zip(targets, top2_preds):
            if target in top_indices:
                top2_correct += 1

    per_class: list[dict[str, Any]] = []
    for index, label in enumerate(label_names):
        tp = int(confusion[index, index])
        fp = int(confusion[:, index].sum() - tp)
        fn = int(confusion[index, :].sum() - tp)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        support = int(confusion[index, :].sum())
        per_class.append(
            {
                "label": label,
                "support": support,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
            }
        )

    macro_precision = float(np.mean([e["precision"] for e in per_class])) if per_class else 0.0
    macro_recall = float(np.mean([e["recall"] for e in per_class])) if per_class else 0.0
    macro_f1 = float(np.mean([e["f1"] for e in per_class])) if per_class else 0.0

    # Micro = aggregate TP/FP/FN across classes
    micro_tp = int(confusion.diagonal().sum())
    micro_fp = int(confusion.sum(axis=0).sum() - micro_tp)
    micro_fn = int(confusion.sum(axis=1).sum() - micro_tp)
    micro_precision = micro_tp / (micro_tp + micro_fp) if (micro_tp + micro_fp) else 0.0
    micro_recall = micro_tp / (micro_tp + micro_fn) if (micro_tp + micro_fn) else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if (micro_precision + micro_recall)
        else 0.0
    )

    return {
        "accuracy": round(correct / total, 4) if total else 0.0,
        "top2_accuracy": round(top2_correct / total, 4) if total else 0.0,
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "macro_f1": round(macro_f1, 4),
        "micro_precision": round(micro_precision, 4),
        "micro_recall": round(micro_recall, 4),
        "micro_f1": round(micro_f1, 4),
        "total": total,
        "confusion_matrix": confusion.tolist(),
        "per_class": per_class,
    }


# ---------------------------------------------------------------------------
# Single-image inference
# ---------------------------------------------------------------------------
def run_single_image_inference(model: Any, metadata: Any, cfg: EvalConfig) -> None:
    from PIL import Image

    img_path = Path(cfg.single_image)
    if not img_path.exists():
        print(f"Image not found: {img_path}")
        return

    image = Image.open(img_path).convert("RGB")
    transform = build_image_transform(image_size=cfg.image_size, train=False)
    tensor = transform(image).unsqueeze(0).to(cfg.device)

    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1)[0].detach().cpu().numpy()

    label_names = metadata.label_names
    allowed_map = load_allowed_map() if cfg.constrained else {}
    idx, confidence, constrained = apply_constraint(
        probs, label_names, cfg.class_name, allowed_map
    )
    display = make_label_display(label_names[idx], metadata.taxonomy)

    print(f"\n{'='*60}")
    print(f"Image: {img_path}")
    print(f"Constrained: {constrained}" + (f" (class={cfg.class_name})" if cfg.class_name else ""))
    print(f"Prediction : {label_names[idx]} (display={display})  conf={confidence:.4f}")
    print(f"{'='*60}")

    topk = top_k_predictions(torch.tensor(probs), label_names, top_k=5)
    print("\nTop-5:")
    for item in topk:
        print(f"  {item['label']:<24} {item['confidence']:.4f}")
    print()


# ---------------------------------------------------------------------------
# Per-sample evaluation (handles both raw & constrained)
# ---------------------------------------------------------------------------
def evaluate_test_set(
    model: Any,
    metadata: Any,
    test_samples: list[DefectSample],
    cfg: EvalConfig,
) -> dict[str, Any]:
    label_names: list[str] = list(metadata.label_names)
    label_to_index = {name: i for i, name in enumerate(label_names)}
    allowed_map = load_allowed_map() if cfg.constrained else {}

    transform = build_image_transform(image_size=cfg.image_size, train=False)
    model.eval()

    predictions: list[int] = []
    targets: list[int] = []
    top2_preds: list[list[int]] = []

    total = len(test_samples)
    print(f"\nRunning evaluation on {total} test samples ...")
    t0 = time.time()

    for idx, sample in enumerate(test_samples):
        if cfg.verbose and (idx + 1) % 50 == 0:
            print(f"  [{idx+1}/{total}]")

        from PIL import Image

        image = Image.open(sample.image_path).convert("RGB")
        mask = Image.open(sample.mask_path)
        roi = crop_roi_with_mask(image, mask, padding_ratio=0.18)

        tensor = transform(roi).unsqueeze(0).to(cfg.device)
        with torch.no_grad():
            logits = model(tensor)
            probs = torch.softmax(logits, dim=1)[0].detach().cpu().numpy()

        best_idx, _, _ = apply_constraint(
            probs, label_names, sample.class_name, allowed_map
        )

        values, indices = torch.tensor(probs).topk(k=min(2, len(label_names)))
        top2_preds.append(indices.tolist())

        predictions.append(best_idx)
        targets.append(label_to_index[sample.label])

    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s ({total / elapsed:.1f} img/s)")

    metrics = compute_metrics(predictions, targets, label_names, top2_preds)
    return metrics


# ---------------------------------------------------------------------------
# Confusion matrix plot
# ---------------------------------------------------------------------------
def plot_confusion_matrix(
    cm: np.ndarray,
    label_names: list[str],
    save_path: Path,
    normalize: bool = True,
) -> None:
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

    plt.figure(figsize=(max(10, len(label_names) * 0.5), max(8, len(label_names) * 0.5)))
    sns.heatmap(
        cm,
        annot=True,
        fmt=".2f" if normalize else "d",
        xticklabels=label_names,
        yticklabels=label_names,
        cmap="Blues",
        cbar=False,
    )
    plt.xlabel("Predicted")
    plt.ylabel("Ground Truth")
    plt.title("Normalized Confusion Matrix" if normalize else "Confusion Matrix")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"  Confusion matrix -> {save_path}")


# ---------------------------------------------------------------------------
# Compare runs
# ---------------------------------------------------------------------------
def compare_runs(cfg: EvalConfig) -> None:
    if not RUNS_ROOT.exists():
        print(f"No runs directory found at {RUNS_ROOT}")
        return

    run_dirs = sorted([d for d in RUNS_ROOT.iterdir() if d.is_dir()])
    if not run_dirs:
        print(f"No runs found under {RUNS_ROOT}")
        return

    # Build a shared test set using the default taxonomy of the script config
    all_samples = discover_defect_samples(cfg.preprocess_root, taxonomy=cfg.taxonomy, split=None)
    if not all_samples:
        print(f"No defect samples found under {cfg.preprocess_root}")
        return
    split = split_samples_by_label(all_samples, seed=DEFAULT_SEED)
    test_samples = split.test

    print(f"\n{'='*70}")
    print(f"Comparing {len(run_dirs)} runs on {len(test_samples)} test samples ...")
    print(f"{'='*70}")

    comparison: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        best_pt = run_dir / "weights" / "best.pt"
        if not best_pt.exists():
            print(f"  Skipping {run_dir.name}: no best.pt")
            continue

        print(f"\n  Evaluating {run_dir.name} ...")
        try:
            model, metadata = load_checkpoint(best_pt, device=cfg.device)
            sample = test_samples[0] if test_samples else None
            image_size = metadata.image_size
            eval_cfg = EvalConfig(
                model_path=best_pt,
                preprocess_root=cfg.preprocess_root,
                taxonomy=metadata.taxonomy,
                image_size=image_size,
                batch=cfg.batch,
                device=cfg.device,
                constrained=cfg.constrained,
                output_dir=cfg.output_dir,
                single_image=None,
                class_name=None,
                save_cm=False,
                compare_runs=False,
            )
            metrics = evaluate_test_set(model, metadata, test_samples, eval_cfg)
            entry = {
                "run_name": run_dir.name,
                "best_pt_path": str(best_pt),
                "taxonomy": metadata.taxonomy,
                "architecture": metadata.architecture,
                "accuracy": metrics["accuracy"],
                "top2_accuracy": metrics["top2_accuracy"],
                "macro_precision": metrics["macro_precision"],
                "macro_recall": metrics["macro_recall"],
                "macro_f1": metrics["macro_f1"],
            }
            comparison.append(entry)
            print(f"    acc={entry['accuracy']:.4f} macro_f1={entry['macro_f1']:.4f}")
        except Exception as exc:
            print(f"    Error: {exc}")
            continue

    if not comparison:
        print("No valid runs to compare.")
        return

    cmp_dir = cfg.output_dir / "comparison"
    cmp_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cmp_dir / "run_comparison.csv"
    json_path = cmp_dir / "run_comparison.json"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison[0].keys()))
        writer.writeheader()
        writer.writerows(comparison)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)

    print(f"\n  Comparison CSV -> {csv_path}")
    print(f"  Comparison JSON -> {json_path}")
    print(f"\n{'Run':<34} {'Acc':<8} {'Top2':<8} {'MacroF1':<8}")
    print("-" * 62)
    for e in comparison:
        print(f"{e['run_name']:<34} {e['accuracy']:<8.4f} {e['top2_accuracy']:<8.4f} {e['macro_f1']:<8.4f}")


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------
def save_reports(metrics: dict[str, Any], cfg: EvalConfig, metadata: Any) -> None:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "config": {
            "model_path": str(cfg.model_path.resolve()),
            "preprocess_root": str(cfg.preprocess_root.resolve()),
            "taxonomy": metadata.taxonomy,
            "architecture": metadata.architecture,
            "image_size": cfg.image_size,
            "device": str(cfg.device),
            "constrained": cfg.constrained,
        },
        "global": {
            "accuracy": metrics["accuracy"],
            "top2_accuracy": metrics["top2_accuracy"],
            "macro_precision": metrics["macro_precision"],
            "macro_recall": metrics["macro_recall"],
            "macro_f1": metrics["macro_f1"],
            "micro_precision": metrics["micro_precision"],
            "micro_recall": metrics["micro_recall"],
            "micro_f1": metrics["micro_f1"],
            "total": metrics["total"],
        },
        "per_class": metrics["per_class"],
        "confusion_matrix": metrics["confusion_matrix"],
    }

    json_path = cfg.output_dir / "defect_type_evaluation_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  Evaluation report -> {json_path}")

    per_class = metrics["per_class"]
    if per_class:
        csv_path = cfg.output_dir / "defect_type_per_class_metrics.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(per_class[0].keys()))
            writer.writeheader()
            writer.writerows(per_class)
        print(f"  Per-class CSV    -> {csv_path}")

    if cfg.save_cm:
        cm = np.asarray(metrics["confusion_matrix"], dtype=np.float32)
        plot_confusion_matrix(cm, metadata.label_names, cfg.output_dir / "confusion_matrix.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    cfg = build_config(parse_args())

    print(f"{'='*60}")
    print("Model 2 (Defect-Type Classifier) Evaluation")
    print(f"{'='*60}")
    print(f"Model:            {cfg.model_path}")
    print(f"Preprocess root:  {cfg.preprocess_root}")
    print(f"Taxonomy:         {cfg.taxonomy}")
    print(f"Device:           {cfg.device}")
    print(f"Constrained:      {cfg.constrained}")
    print(f"Output dir:       {cfg.output_dir}")

    # --- Compare runs mode ---
    if cfg.compare_runs:
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        compare_runs(cfg)
        return 0

    # --- Load model ---
    if not cfg.model_path.exists():
        print(f"Model not found: {cfg.model_path}")
        return 1

    try:
        model, metadata = load_checkpoint(cfg.model_path, device=cfg.device)
    except Exception as exc:
        print(f"Failed to load checkpoint: {exc}")
        return 1

    # Honor the taxonomy stored in the checkpoint if user didn't override semantics.
    taxonomy = metadata.taxonomy
    print(f"\nLoaded classifier: arch={metadata.architecture} taxonomy={taxonomy} "
          f"num_classes={len(metadata.label_names)} image_size={metadata.image_size}")

    # --- Single-image mode ---
    if cfg.single_image:
        run_single_image_inference(model, metadata, cfg)
        return 0

    # --- Discover test samples (use the checkpoint's taxonomy for GT labels) ---
    all_samples = discover_defect_samples(cfg.preprocess_root, taxonomy=taxonomy, split=None)
    if not all_samples:
        print(f"No defect samples found under {cfg.preprocess_root}. Run preprocessing first.")
        return 1

    split = split_samples_by_label(all_samples, seed=DEFAULT_SEED)
    test_samples = split.test
    print(f"\nTest samples: {len(test_samples)} (of {len(all_samples)} total defect samples)")

    if not test_samples:
        print("No test samples available.")
        return 1

    # Evaluate with the checkpoint's image size (override by CLI if provided)
    if cfg.image_size is None:
        cfg.image_size = metadata.image_size

    metrics = evaluate_test_set(model, metadata, test_samples, cfg)

    save_reports(metrics, cfg, metadata)

    # --- Print summary ---
    print(f"\n{'='*60}")
    print("SUMMARY" + (" (constrained)" if cfg.constrained else ""))
    print(f"{'='*60}")
    print(f"  Accuracy        : {metrics['accuracy']:.4f}")
    print(f"  Top-2 Accuracy  : {metrics['top2_accuracy']:.4f}")
    print(f"  Macro Precision : {metrics['macro_precision']:.4f}")
    print(f"  Macro Recall    : {metrics['macro_recall']:.4f}")
    print(f"  Macro F1        : {metrics['macro_f1']:.4f}")
    print(f"  Micro F1        : {metrics['micro_f1']:.4f}")

    print(f"\n  Per-class (top by support):")
    for entry in sorted(metrics["per_class"], key=lambda e: e["support"], reverse=True):
        if entry["support"] == 0:
            continue
        print(f"    {entry['label']:<22} sup={entry['support']:<4} "
              f"P={entry['precision']:.3f} R={entry['recall']:.3f} F1={entry['f1']:.3f}")

    print(f"\nAll results saved to: {cfg.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())