from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_PROJECT_NAME = "ai-segmentation"
DEFAULT_MODEL = "yolo11n-seg.pt"
DEFAULT_IMAGE_SIZE = 416
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
    image_size = int(dataset_meta.get("image_size", config.imgsz))
    if config.imgsz == DEFAULT_IMAGE_SIZE:
        config = TrainConfig(**{**config.__dict__, "imgsz": image_size})

    validate_dataset_layout(config.preprocess_root)
    validate_label_coverage(config.preprocess_root)
    data_yaml_path = write_data_yaml(config, dataset_meta)
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
        "close_mosaic": 10,
        "cos_lr": True,
        "mosaic": 0.1 if not config.smoke_test else 0.0,
        "mixup": 0.0,
        "copy_paste": 0.0,
        "fliplr": 0.5,
        "flipud": 0.1,
        "degrees": 5.0,
        "translate": 0.05,
        "scale": 0.1,
        "shear": 0.0,
        "hsv_h": 0.015,
        "hsv_s": 0.4,
        "hsv_v": 0.2,
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