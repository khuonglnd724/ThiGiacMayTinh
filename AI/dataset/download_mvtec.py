from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


@dataclass(frozen=True)
class SampleRecord:
    class_name: str
    split: str
    label: str
    image_path: str
    mask_path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and prepare MVTec AD dataset.")
    parser.add_argument("--dataset-root", default="mvtec-ad", help="Target dataset root.")
    parser.add_argument("--source", choices=["kaggle", "local"], default="local", help="Dataset source.")
    parser.add_argument("--kaggle-dataset", default="ipythonx/mvtec-ad", help="Kaggle dataset id.")
    parser.add_argument("--local-source", default="", help="Optional local source directory to copy from.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic seed for split generation.")
    parser.add_argument("--train-ratio", type=float, default=0.7, help="Train split ratio.")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation split ratio.")
    parser.add_argument("--test-ratio", type=float, default=0.1, help="Test split ratio.")
    parser.add_argument("--manifest-name", default="manifest.json", help="Manifest filename.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_root = Path(args.dataset_root)
    raw_root = dataset_root / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)

    if args.source == "kaggle":
        download_from_kaggle(args.kaggle_dataset, raw_root)
    elif args.local_source:
        copy_local_source(Path(args.local_source), raw_root)

    class_dirs = discover_class_dirs(raw_root)
    if not class_dirs:
        print(f"No class folders found in {raw_root}. Place MVTec AD data there first or use --source kaggle.")
        return 1

    records = build_manifest(class_dirs, args.seed, args.train_ratio, args.val_ratio, args.test_ratio)
    write_outputs(dataset_root, records, args.manifest_name)
    print(f"Prepared {len(records)} records under {dataset_root}")
    return 0


def download_from_kaggle(dataset_id: str, destination: Path) -> None:
    try:
        import kaggle  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "The kaggle package is not installed. Install it first, then provide Kaggle credentials."
        ) from exc

    command = [
        sys.executable,
        "-m",
        "kaggle",
        "datasets",
        "download",
        "-d",
        dataset_id,
        "-p",
        str(destination),
        "--unzip",
    ]
    subprocess.run(command, check=True)


def copy_local_source(source_root: Path, destination: Path) -> None:
    if not source_root.exists():
        raise SystemExit(f"Local source directory not found: {source_root}")
    for item in source_root.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def discover_class_dirs(raw_root: Path) -> list[Path]:
    class_dirs: list[Path] = []
    for child in sorted(raw_root.iterdir()):
        if child.is_dir() and child.name != "manifest":
            class_dirs.append(child)
    return class_dirs


def build_manifest(
    class_dirs: Iterable[Path],
    seed: int,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
) -> list[SampleRecord]:
    if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 1e-6:
        raise SystemExit("Train/Val/Test ratios must sum to 1.0")

    rng = random.Random(seed)
    records: list[SampleRecord] = []
    for class_dir in class_dirs:
        samples = collect_samples_for_class(class_dir)
        rng.shuffle(samples)
        train_cutoff = int(len(samples) * train_ratio)
        val_cutoff = train_cutoff + int(len(samples) * val_ratio)

        for index, sample in enumerate(samples):
            if index < train_cutoff:
                split = "train"
            elif index < val_cutoff:
                split = "val"
            else:
                split = "test"
            records.append(
                SampleRecord(
                    class_name=class_dir.name,
                    split=split,
                    label=sample["label"],
                    image_path=str(sample["image_path"]),
                    mask_path=str(sample["mask_path"]),
                )
            )
    return records


def collect_samples_for_class(class_dir: Path) -> list[dict[str, Path | str]]:
    samples: list[dict[str, Path | str]] = []
    for split_name in ("train", "test"):
        split_dir = class_dir / split_name
        if not split_dir.exists():
            continue

        for anomaly_dir in sorted(child for child in split_dir.iterdir() if child.is_dir()):
            anomaly_type = anomaly_dir.name
            is_good = anomaly_type.lower() == "good"

            for image_path in sorted(anomaly_dir.rglob("*")):
                if image_path.is_dir() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue

                if is_good:
                    label = "good"
                    mask_path: Path | str = ""
                else:
                    label = "defect"
                    mask_path = find_mask_path(class_dir, anomaly_type, image_path)

                samples.append({"image_path": image_path, "mask_path": mask_path, "label": label})
    return samples


def find_mask_path(class_dir: Path, anomaly_type: str, image_path: Path) -> Path | str:
    mask_candidates = [
        class_dir / "ground_truth" / anomaly_type / f"{image_path.stem}_mask.png",
        class_dir / "ground_truth" / anomaly_type / f"{image_path.stem}_mask{image_path.suffix}",
    ]
    for candidate in mask_candidates:
        if candidate.exists():
            return candidate
    return ""


def write_outputs(dataset_root: Path, records: list[SampleRecord], manifest_name: str) -> None:
    manifest_dir = dataset_root / "manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    csv_path = manifest_dir / "manifest.csv"
    json_path = manifest_dir / manifest_name

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["class_name", "split", "label", "image_path", "mask_path"])
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))

    with json_path.open("w", encoding="utf-8") as json_file:
        json.dump([asdict(record) for record in records], json_file, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())