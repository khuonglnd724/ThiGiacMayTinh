from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, WeightedRandomSampler

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from AI.defect_type.dataset import DefectSample, collect_label_names, discover_defect_samples, summarize_samples, DefectTypeDataset, split_samples_by_label
from AI.defect_type.model_utils import build_model, load_checkpoint


DEFAULT_OUTPUT_DIR = Path("runs/classify/AI/defect-type")


@dataclass(frozen=True)
class TrainConfig:
    preprocess_root: Path
    output_dir: Path
    taxonomy: str
    architecture: str
    image_size: int
    batch_size: int
    epochs: int
    lr: float
    weight_decay: float
    num_workers: int
    device: str
    seed: int
    smoke_test: bool
    padding_ratio: float
    pretrained: bool
    sample_limit: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a second-stage defect-type classifier.")
    parser.add_argument("--preprocess-root", default="AI/preprocess/output", help="Path to the current preprocessing output root.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for classifier checkpoints and reports.")
    parser.add_argument("--taxonomy", choices=["composite", "global"], default="composite", help="Label strategy for the classifier.")
    parser.add_argument("--architecture", choices=["mobilenet_v3_small", "resnet18", "efficientnet_b0"], default="mobilenet_v3_small", help="Backbone architecture.")
    parser.add_argument("--image-size", type=int, default=224, help="ROI crop size used for training and inference.")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size.")
    parser.add_argument("--epochs", type=int, default=12, help="Number of epochs.")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate.")
    parser.add_argument("--weight-decay", type=float, default=1e-4, help="Weight decay.")
    parser.add_argument("--num-workers", type=int, default=4, help="Dataloader workers.")
    parser.add_argument("--device", default="auto", help='Device: "auto", "cpu", "cuda", or CUDA index.')
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--smoke-test", action="store_true", help="Run a minimal training pass to validate the pipeline.")
    parser.add_argument("--padding-ratio", type=float, default=0.18, help="Padding applied around defect mask bbox.")
    parser.add_argument("--pretrained", action=argparse.BooleanOptionalAction, default=True, help="Use ImageNet pretrained weights when available.")
    parser.add_argument("--sample-limit", type=int, default=0, help="Optional cap for each split to smoke test the pipeline quickly.")
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> TrainConfig:
    return TrainConfig(
        preprocess_root=Path(args.preprocess_root),
        output_dir=Path(args.output_dir),
        taxonomy=args.taxonomy,
        architecture=args.architecture,
        image_size=args.image_size,
        batch_size=1 if args.smoke_test else args.batch_size,
        epochs=1 if args.smoke_test else args.epochs,
        lr=args.lr,
        weight_decay=args.weight_decay,
        num_workers=0 if args.smoke_test else args.num_workers,
        device=args.device,
        seed=args.seed,
        smoke_test=bool(args.smoke_test),
        padding_ratio=args.padding_ratio,
        pretrained=bool(args.pretrained),
        sample_limit=max(0, args.sample_limit),
    )


def resolve_device(device: str) -> torch.device:
    if device != "auto":
        return torch.device(device)
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def set_seed(seed: int) -> None:
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_dataloaders(
    config: TrainConfig,
    train_samples: list[DefectSample],
    val_samples: list[DefectSample],
    test_samples: list[DefectSample],
    label_names: list[str],
) -> tuple[DataLoader, DataLoader, DataLoader, dict[str, int]]:
    if config.sample_limit > 0:
        train_samples = train_samples[: config.sample_limit]
        val_samples = val_samples[: max(1, min(config.sample_limit // 4 or 1, len(val_samples)))]
        test_samples = test_samples[: max(1, min(config.sample_limit // 4 or 1, len(test_samples)))]

    label_to_index = {label: index for index, label in enumerate(label_names)}

    train_dataset = DefectTypeDataset(train_samples, label_to_index, image_size=config.image_size, train=True, padding_ratio=config.padding_ratio)
    val_dataset = DefectTypeDataset(val_samples, label_to_index, image_size=config.image_size, train=False, padding_ratio=config.padding_ratio)
    test_dataset = DefectTypeDataset(test_samples, label_to_index, image_size=config.image_size, train=False, padding_ratio=config.padding_ratio)

    train_dataset.label_names = label_names  # type: ignore[attr-defined]
    val_dataset.label_names = label_names  # type: ignore[attr-defined]
    test_dataset.label_names = label_names  # type: ignore[attr-defined]

    sample_weights = []
    train_counts = summarize_samples(train_samples)["counts"]
    for sample in train_samples:
        sample_weights.append(1.0 / max(1, train_counts.get(sample.label, 1)))
    sampler = WeightedRandomSampler(weights=sample_weights, num_samples=max(len(train_samples), len(train_samples) * 2), replacement=True) if train_samples else None

    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=(sampler is None), sampler=sampler, num_workers=config.num_workers, pin_memory=torch.cuda.is_available())
    val_loader = DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False, num_workers=config.num_workers, pin_memory=torch.cuda.is_available())
    test_loader = DataLoader(test_dataset, batch_size=config.batch_size, shuffle=False, num_workers=config.num_workers, pin_memory=torch.cuda.is_available())
    return train_loader, val_loader, test_loader, label_to_index


def compute_class_weights(train_samples: list[DefectSample], label_to_index: dict[str, int]) -> torch.Tensor:
    counts = np.zeros(len(label_to_index), dtype=np.float32)
    for sample in train_samples:
        counts[label_to_index[sample.label]] += 1.0
    counts[counts == 0] = 1.0
    weights = counts.sum() / counts
    weights = weights / weights.mean()
    return torch.tensor(weights, dtype=torch.float32)


def compute_metrics(logits: torch.Tensor, targets: torch.Tensor, label_names: list[str]) -> dict[str, Any]:
    probabilities = torch.softmax(logits, dim=1)
    predictions = torch.argmax(probabilities, dim=1)
    top2 = torch.topk(probabilities, k=min(2, probabilities.shape[1]), dim=1).indices

    num_classes = len(label_names)
    confusion = np.zeros((num_classes, num_classes), dtype=np.int64)
    for target, prediction in zip(targets.tolist(), predictions.tolist()):
        confusion[target, prediction] += 1

    per_class = []
    total = confusion.sum()
    correct = int(np.trace(confusion))
    top2_correct = 0
    for target, top_indices in zip(targets.tolist(), top2.tolist()):
        if target in top_indices:
            top2_correct += 1

    for index, label in enumerate(label_names):
        tp = int(confusion[index, index])
        fp = int(confusion[:, index].sum() - tp)
        fn = int(confusion[index, :].sum() - tp)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        support = int(confusion[index, :].sum())
        per_class.append(
            {
                "label": label,
                "support": support,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )

    macro_precision = float(np.mean([entry["precision"] for entry in per_class])) if per_class else 0.0
    macro_recall = float(np.mean([entry["recall"] for entry in per_class])) if per_class else 0.0
    macro_f1 = float(np.mean([entry["f1"] for entry in per_class])) if per_class else 0.0

    return {
        "accuracy": correct / total if total else 0.0,
        "top2_accuracy": top2_correct / total if total else 0.0,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "confusion_matrix": confusion.tolist(),
        "per_class": per_class,
    }


def run_epoch(model: nn.Module, loader: DataLoader, criterion: nn.Module, device: torch.device, optimizer: torch.optim.Optimizer | None = None) -> dict[str, Any]:
    is_train = optimizer is not None
    model.train(is_train)

    all_logits: list[torch.Tensor] = []
    all_targets: list[torch.Tensor] = []
    total_loss = 0.0
    total_count = 0

    for images, targets in loader:
        images = images.to(device)
        targets = targets.to(device)

        if is_train:
            optimizer.zero_grad(set_to_none=True)

        with torch.set_grad_enabled(is_train):
            logits = model(images)
            loss = criterion(logits, targets)
            if is_train:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
                optimizer.step()

        batch_size = images.size(0)
        total_loss += float(loss.item()) * batch_size
        total_count += batch_size
        all_logits.append(logits.detach().cpu())
        all_targets.append(targets.detach().cpu())

    logits_tensor = torch.cat(all_logits, dim=0) if all_logits else torch.empty(0)
    targets_tensor = torch.cat(all_targets, dim=0) if all_targets else torch.empty(0, dtype=torch.long)
    metrics = compute_metrics(logits_tensor, targets_tensor, loader.dataset.label_names if hasattr(loader.dataset, "label_names") else [])
    metrics["loss"] = total_loss / total_count if total_count else 0.0
    return metrics


def attach_label_names(dataset: DefectTypeDataset, label_names: list[str]) -> None:
    dataset.label_names = label_names  # type: ignore[attr-defined]


def build_model_bundle(config: TrainConfig, label_names: list[str], device: torch.device) -> nn.Module:
    model = build_model(config.architecture, len(label_names), pretrained=config.pretrained)
    return model.to(device)


def save_checkpoint(path: Path, model: nn.Module, config: TrainConfig, label_names: list[str], best_metrics: dict[str, Any], label_to_index: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "architecture": config.architecture,
        "taxonomy": config.taxonomy,
        "image_size": config.image_size,
        "label_names": label_names,
        "label_to_index": label_to_index,
        "state_dict": model.state_dict(),
        "best_metrics": best_metrics,
    }
    torch.save(payload, path)


def main() -> int:
    args = parse_args()
    config = build_config(args)
    set_seed(config.seed)
    device = resolve_device(config.device)

    all_samples = discover_defect_samples(config.preprocess_root, taxonomy=config.taxonomy, split=None)
    label_names = collect_label_names(all_samples)
    split_result = split_samples_by_label(all_samples, seed=config.seed)
    train_samples, val_samples, test_samples = split_result.train, split_result.val, split_result.test

    if not all_samples:
        raise SystemExit(f"No defect samples found under {config.preprocess_root}. Run preprocessing first.")

    train_loader, val_loader, test_loader, label_to_index = build_dataloaders(config, train_samples, val_samples, test_samples, label_names)

    class_weights = compute_class_weights(train_samples, label_to_index).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=0.05)
    model = build_model_bundle(config, label_names, device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, config.epochs))

    run_dir = config.output_dir / f"{config.architecture}-{config.taxonomy}"
    run_dir.mkdir(parents=True, exist_ok=True)
    weights_dir = run_dir / "weights"
    history: list[dict[str, Any]] = []
    best_state: dict[str, Any] | None = None
    best_score = -1.0

    summary = {
        "train": summarize_samples(train_samples),
        "val": summarize_samples(val_samples),
        "test": summarize_samples(test_samples),
        "label_names": label_names,
        "taxonomy": config.taxonomy,
        "architecture": config.architecture,
    }
    (run_dir / "dataset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    for epoch in range(1, config.epochs + 1):
        train_metrics = run_epoch(model, train_loader, criterion, device, optimizer=optimizer)
        val_metrics = run_epoch(model, val_loader, criterion, device, optimizer=None)
        scheduler.step()

        record = {
            "epoch": epoch,
            "train": train_metrics,
            "val": val_metrics,
            "lr": scheduler.get_last_lr()[0],
        }
        history.append(record)

        score = float(val_metrics.get("macro_f1", 0.0))
        if score >= best_score:
            best_score = score
            best_state = {
                "architecture": config.architecture,
                "taxonomy": config.taxonomy,
                "image_size": config.image_size,
                "label_names": label_names,
                "label_to_index": label_to_index,
                "state_dict": model.state_dict(),
                "best_metrics": val_metrics,
                "epoch": epoch,
            }
            save_checkpoint(weights_dir / "best.pt", model, config, label_names, val_metrics, label_to_index)

        print(
            f"Epoch {epoch:03d} | train_loss={train_metrics['loss']:.4f} train_f1={train_metrics['macro_f1']:.4f} "
            f"val_loss={val_metrics['loss']:.4f} val_f1={val_metrics['macro_f1']:.4f} val_acc={val_metrics['accuracy']:.4f}"
        )

    save_checkpoint(weights_dir / "last.pt", model, config, label_names, history[-1]["val"] if history else {}, label_to_index)

    if best_state is None:
        best_state = {
            "architecture": config.architecture,
            "taxonomy": config.taxonomy,
            "image_size": config.image_size,
            "label_names": label_names,
            "label_to_index": label_to_index,
            "state_dict": model.state_dict(),
            "best_metrics": history[-1]["val"] if history else {},
            "epoch": config.epochs,
        }

    test_metrics = run_epoch(model, test_loader, criterion, device, optimizer=None)
    report = {
        "config": {
            "preprocess_root": str(config.preprocess_root.resolve()),
            "output_dir": str(config.output_dir.resolve()),
            "taxonomy": config.taxonomy,
            "architecture": config.architecture,
            "image_size": config.image_size,
            "batch_size": config.batch_size,
            "epochs": config.epochs,
            "lr": config.lr,
            "weight_decay": config.weight_decay,
            "padding_ratio": config.padding_ratio,
        },
        "best_epoch": best_state.get("epoch", 0),
        "best_val_metrics": best_state.get("best_metrics", {}),
        "test_metrics": test_metrics,
        "history": history,
    }
    (run_dir / "training_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "label_map.json").write_text(json.dumps({str(i): label for i, label in enumerate(label_names)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved classifier run to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
