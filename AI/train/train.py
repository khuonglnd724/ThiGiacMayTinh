from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_PROJECT_NAME = "ai-segmentation"
DEFAULT_MODEL = "yolo11n-seg.pt"
DEFAULT_IMAGE_SIZE = 640
DEFAULT_BATCH_SIZE = 2
DEFAULT_EPOCHS = 50
DEFAULT_ACCUMULATE = 8
DEFAULT_WORKERS = 4
DEFAULT_LR0 = 1e-4
DEFAULT_WEIGHT_DECAY = 1e-2


@dataclass(frozen=True)
class TrainConfig:
    project_root: Path
    preprocess_root: Path
    data_yaml_path: Path
    model: str
    imgsz: int
    batch: int
    epochs: int
    device: str
    workers: int
    amp: bool
    accumulate: int
    seed: int
    optimizer: str
    lr0: float
    weight_decay: float
    patience: int
    project_name: str
    run_name: str
    smoke_test: bool
    cache: bool
    val: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a YOLO segmentation model on the preprocessed MVTec AD dataset.")
    parser.add_argument("--project-root", default="AI/train", help="Folder that stores this training script and outputs.")
    parser.add_argument("--preprocess-root", default="AI/preprocess/output", help="Root folder created by the preprocessing step.")
    parser.add_argument("--data-yaml", default="", help="Optional explicit path to a YOLO data.yaml file.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Pretrained segmentation checkpoint to fine-tune.")
    parser.add_argument("--imgsz", type=int, default=DEFAULT_IMAGE_SIZE, help="Working image size.")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH_SIZE, help="Batch size for the GPU.")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS, help="Number of training epochs.")
    parser.add_argument("--device", default="auto", help="Torch device, e.g. auto, 0, cpu.")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Dataloader workers.")
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True, help="Enable mixed precision training.")
    parser.add_argument("--accumulate", type=int, default=DEFAULT_ACCUMULATE, help="Gradient accumulation steps for small VRAM.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument("--optimizer", default="AdamW", help="Optimizer to use during fine-tuning.")
    parser.add_argument("--lr0", type=float, default=DEFAULT_LR0, help="Initial learning rate.")
    parser.add_argument("--weight-decay", type=float, default=DEFAULT_WEIGHT_DECAY, help="Weight decay for AdamW.")
    parser.add_argument("--patience", type=int, default=20, help="Early stopping patience.")
    parser.add_argument("--project-name", default=DEFAULT_PROJECT_NAME, help="Ultralytics project name for run outputs.")
    parser.add_argument("--run-name", default="segmentation", help="Run name for the current experiment.")
    parser.add_argument("--smoke-test", action="store_true", help="Run a very small training pass to validate the pipeline.")
    parser.add_argument("--cache", action="store_true", help="Cache dataset images in RAM if memory allows it.")
    parser.add_argument("--no-val", action="store_true", help="Disable validation during training.")
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> TrainConfig:
    project_root = Path(args.project_root)
    preprocess_root = Path(args.preprocess_root)
    data_yaml_path = Path(args.data_yaml) if args.data_yaml else project_root / "data.yaml"
    return TrainConfig(
        project_root=project_root,
        preprocess_root=preprocess_root,
        data_yaml_path=data_yaml_path,
        model=args.model,
        imgsz=args.imgsz,
        batch=args.batch,
        epochs=args.epochs,
        device=args.device,
        workers=args.workers,
        amp=bool(args.amp),
        accumulate=max(1, args.accumulate),
        seed=args.seed,
        optimizer=args.optimizer,
        lr0=args.lr0,
        weight_decay=args.weight_decay,
        patience=args.patience,
        project_name=args.project_name,
        run_name=args.run_name,
        smoke_test=bool(args.smoke_test),
        cache=bool(args.cache),
        val=not args.no_val,
    )


def main() -> int:
    config = build_config(parse_args())
    dataset_meta = load_preprocess_metadata(config.preprocess_root)

    validate_dataset_layout(config.preprocess_root)
    validate_label_coverage(config.preprocess_root)
    quality_report = audit_dataset_quality(config.preprocess_root, dataset_meta)
    data_yaml_path = write_data_yaml(config, dataset_meta)
    write_quality_report(config, quality_report)
    summarize_dataset(config.preprocess_root, data_yaml_path)

    train_kwargs = build_ultralytics_kwargs(config, data_yaml_path)
    run_training(config.model, train_kwargs)
    return 0


def load_preprocess_metadata(preprocess_root: Path) -> dict[str, Any]:
    meta_path = preprocess_root / "meta" / "preprocess_config.json"
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def validate_dataset_layout(preprocess_root: Path) -> None:
    required_dirs = [
        preprocess_root / "images" / "train",
        preprocess_root / "images" / "val",
        preprocess_root / "images" / "test",
        preprocess_root / "labels" / "train",
        preprocess_root / "labels" / "val",
        preprocess_root / "labels" / "test",
    ]
    missing = [str(path) for path in required_dirs if not path.exists()]
    if missing:
        raise SystemExit("Missing preprocessed dataset folders:\n- " + "\n- ".join(missing))


def validate_label_coverage(preprocess_root: Path) -> None:
    split_non_empty: dict[str, int] = {}
    for split in ("train", "val"):
        label_root = preprocess_root / "labels" / split
        non_empty_count = 0
        for label_file in label_root.rglob("*.txt"):
            if label_file.is_file() and label_file.read_text(encoding="utf-8").strip():
                non_empty_count += 1
        split_non_empty[split] = non_empty_count

    if split_non_empty["train"] == 0 and split_non_empty["val"] == 0:
        raise SystemExit(
            "No positive segmentation labels found in both train and val splits. "
            "Regenerate manifest/preprocess outputs before training."
        )


def audit_dataset_quality(preprocess_root: Path, dataset_meta: dict[str, Any]) -> dict[str, Any]:
    manifest_path = dataset_meta.get("manifest_path")
    dataset_root = dataset_meta.get("dataset_root")
    report: dict[str, Any] = {
        "preprocess_root": preprocess_root.resolve().as_posix(),
        "manifest_path": manifest_path,
        "splits": {},
        "issues": [],
    }

    if not manifest_path:
        report["issues"].append("Missing manifest_path in preprocess metadata.")
        return report

    manifest_file = Path(manifest_path)
    if not manifest_file.is_absolute():
        if dataset_root:
            manifest_file = Path(dataset_root) / manifest_file
        else:
            manifest_file = preprocess_root.parent.parent / manifest_file

    if not manifest_file.exists():
        report["issues"].append(f"Manifest not found: {manifest_file}")
        return report

    manifest = load_manifest_records(manifest_file)
    too_few_defect_classes: list[dict[str, Any]] = []

    for split in ("train", "val", "test"):
        split_records = [record for record in manifest if record["split"] == split]
        class_counts: dict[str, dict[str, int]] = {}
        empty_defect_masks = 0
        missing_images = 0
        missing_labels = 0
        mismatched_masks = 0

        for record in split_records:
            class_name = record["class_name"]
            class_counts.setdefault(class_name, {"good": 0, "defect": 0})
            class_counts[class_name][record["label"]] += 1

            image_path, label_path, mask_path = expected_output_paths(preprocess_root, record)
            if not image_path.exists():
                missing_images += 1
            if not label_path.exists():
                missing_labels += 1
            if record["label"] == "defect":
                if not mask_path.exists():
                    empty_defect_masks += 1
                else:
                    with Image.open(mask_path) as mask_file:
                        if mask_file.getextrema()[1] == 0:
                            empty_defect_masks += 1

            if image_path.exists() and mask_path.exists():
                try:
                    with Image.open(image_path) as image_file, Image.open(mask_path) as mask_file:
                        if image_file.size != mask_file.size:
                            mismatched_masks += 1
                except Exception:
                    mismatched_masks += 1

        for class_name, counts in class_counts.items():
            if counts["defect"] > 0 and counts["defect"] < 5:
                too_few_defect_classes.append(
                    {"split": split, "class_name": class_name, "defect_samples": counts["defect"]}
                )

        report["splits"][split] = {
            "total_samples": len(split_records),
            "class_counts": class_counts,
            "missing_images": missing_images,
            "missing_labels": missing_labels,
            "empty_defect_masks": empty_defect_masks,
            "mismatched_masks": mismatched_masks,
        }

    report["too_few_defect_classes"] = too_few_defect_classes
    if too_few_defect_classes:
        report["issues"].append("Some classes have fewer than 5 defect samples in a split.")
    return report


def load_manifest_records(manifest_file: Path) -> list[dict[str, Any]]:
    if manifest_file.suffix.lower() == ".json":
        return json.loads(manifest_file.read_text(encoding="utf-8"))

    if manifest_file.suffix.lower() == ".csv":
        with manifest_file.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return [row for row in reader]

    raise SystemExit(f"Unsupported manifest format: {manifest_file.suffix}")


def expected_output_paths(preprocess_root: Path, record: dict[str, Any]) -> tuple[Path, Path, Path]:
    base_name = Path(record["image_path"]).stem
    class_name = record["class_name"]
    split = record["split"]
    image_path = preprocess_root / "images" / split / class_name / f"{base_name}.jpg"
    label_path = preprocess_root / "labels" / split / class_name / f"{base_name}.txt"
    mask_path = preprocess_root / "masks" / split / class_name / f"{base_name}.png"
    return image_path, label_path, mask_path


def write_quality_report(config: TrainConfig, report: dict[str, Any]) -> None:
    report_path = config.project_root / "dataset_quality_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dataset quality report saved to: {report_path}")
    for split, summary in report.get("splits", {}).items():
        print(
            f"  {split}: total={summary['total_samples']}, empty_defect_masks={summary['empty_defect_masks']}, "
            f"mismatched_masks={summary['mismatched_masks']}"
        )
    if report.get("too_few_defect_classes"):
        print("  Warning: some class/split combinations have fewer than 5 defect samples.")


def write_data_yaml(config: TrainConfig, dataset_meta: dict[str, Any]) -> Path:
    config.project_root.mkdir(parents=True, exist_ok=True)
    data_yaml_path = config.data_yaml_path
    data_yaml_path.parent.mkdir(parents=True, exist_ok=True)

    dataset_root = config.preprocess_root.resolve().as_posix()
    yaml_text = "\n".join(
        [
            f"path: {dataset_root}",
            "train: images/train",
            "val: images/val",
            "test: images/test",
            "nc: 1",
            "names:",
            "  0: defect",
            "",
        ]
    )
    data_yaml_path.write_text(yaml_text, encoding="utf-8")

    info_path = config.project_root / "dataset_summary.json"
    summary = {
        "dataset_root": dataset_root,
        "data_yaml_path": data_yaml_path.resolve().as_posix(),
        "image_size": dataset_meta.get("image_size", config.imgsz),
        "normalization": dataset_meta.get("normalization", "imagenet"),
        "splits": count_split_samples(config.preprocess_root),
    }
    info_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return data_yaml_path


def count_split_samples(preprocess_root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for split in ("train", "val", "test"):
        image_root = preprocess_root / "images" / split
        total = 0
        if image_root.exists():
            for file_path in image_root.rglob("*.jpg"):
                if file_path.is_file():
                    total += 1
        counts[split] = total
    return counts


def summarize_dataset(preprocess_root: Path, data_yaml_path: Path) -> None:
    split_counts = count_split_samples(preprocess_root)
    print("Dataset summary:")
    for split, total in split_counts.items():
        print(f"  {split}: {total}")
    print(f"YOLO data file: {data_yaml_path}")


def build_ultralytics_kwargs(config: TrainConfig, data_yaml_path: Path) -> dict[str, Any]:
    imgsz = min(config.imgsz, 320) if config.smoke_test else config.imgsz
    batch = 1 if config.smoke_test else config.batch
    epochs = 1 if config.smoke_test else config.epochs
    workers = 0 if config.smoke_test else config.workers

    return {
        "data": str(data_yaml_path),
        "imgsz": imgsz,
        "batch": batch,
        "epochs": epochs,
        "device": resolve_device(config.device),
        "workers": workers,
        "amp": False if config.smoke_test else config.amp,
        "optimizer": config.optimizer,
        "lr0": config.lr0,
        "weight_decay": config.weight_decay,
        "patience": config.patience,
        "project": str(config.project_root / "runs" / config.project_name),
        "name": config.run_name + ("-smoke" if config.smoke_test else ""),
        "exist_ok": True,
        "pretrained": True,
        "seed": config.seed,
        "cache": config.cache if not config.smoke_test else False,
        "val": config.val,
        "plots": True,
        "save": True,
        "close_mosaic": 0,
        "cos_lr": True,
        "mosaic": 0.0,
        "mixup": 0.0,
        "copy_paste": 0.0,
        "fliplr": 0.5,
        "flipud": 0.0,
        "degrees": 2.0,
        "translate": 0.02,
        "scale": 0.05,
        "shear": 0.0,
        "hsv_h": 0.01,
        "hsv_s": 0.2,
        "hsv_v": 0.15,
        "nbs": max(config.batch * config.accumulate, config.batch),
    }


def resolve_device(device: str) -> str:
    if device != "auto":
        return device

    try:
        import torch
    except ImportError:
        return "cpu"

    return "0" if torch.cuda.is_available() else "cpu"


def run_training(model_name: str, train_kwargs: dict[str, Any]) -> None:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "ultralytics is not installed. Install dependencies from plan 4 before running training."
        ) from exc

    model = YOLO(model_name)
    results = model.train(**train_kwargs)
    save_dir = getattr(results, "save_dir", None)
    if save_dir is not None:
        print(f"Training artifacts saved to: {save_dir}")
        print(f"Best checkpoint should be under: {Path(save_dir) / 'weights' / 'best.pt'}")


if __name__ == "__main__":
    raise SystemExit(main())