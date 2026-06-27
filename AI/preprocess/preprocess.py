from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageEnhance, ImageOps


IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
DEFAULT_IMAGE_SIZE = 640
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass(frozen=True)
class ManifestRecord:
    class_name: str
    split: str
    label: str
    image_path: str
    mask_path: str


@dataclass(frozen=True)
class PreprocessConfig:
    dataset_root: Path
    manifest_path: Path
    output_root: Path
    image_size: int = DEFAULT_IMAGE_SIZE
    seed: int = 42
    augment_count: int = 3
    normalization: str = "imagenet"
    save_augmented_train_only: bool = True
    good_ratio: float = 0.1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess MVTec AD into YOLO-ready segmentation data.")
    parser.add_argument("--dataset-root", default="AI/dataset/mvtec-ad", help="Path to the MVTec AD dataset root.")
    parser.add_argument("--manifest", default="AI/dataset/mvtec-ad/manifest/manifest.json", help="Manifest CSV/JSON path.")
    parser.add_argument("--output-root", default="AI/preprocess/output", help="Directory for processed data.")
    parser.add_argument(
        "--image-size",
        type=int,
        default=DEFAULT_IMAGE_SIZE,
        help="Reference size recorded in metadata; original images are preserved.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for augmentation.")
    parser.add_argument("--augment-count", type=int, default=1, help="Augmented copies to generate per train sample.")
    parser.add_argument(
        "--normalization",
        choices=["none", "minmax", "imagenet"],
        default="imagenet",
        help="Normalization mode for runtime statistics.",
    )
    parser.add_argument(
        "--augment-train-only",
        action="store_true",
        default=True,
        help="Write augmented samples only for train split.",
    )
    parser.add_argument(
        "--good-ratio",
        type=float,
        default=0.1,
        help="Fraction of 'good' samples to keep per class relative to defect count (0.1 = 10%%). Set to -1 to keep all.",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> PreprocessConfig:
    return PreprocessConfig(
        dataset_root=Path(args.dataset_root),
        manifest_path=Path(args.manifest),
        output_root=Path(args.output_root),
        image_size=args.image_size,
        seed=args.seed,
        augment_count=max(0, args.augment_count),
        normalization=args.normalization,
        save_augmented_train_only=args.augment_train_only,
        good_ratio=args.good_ratio,
    )


def main() -> int:
    config = build_config(parse_args())
    rng = random.Random(config.seed)
    np.random.seed(config.seed)

    records = load_manifest(config.manifest_path)
    if not records:
        print(f"No manifest records found in {config.manifest_path}")
        return 1

    categories = sorted(list({r.class_name for r in records}))
    class_to_id = {cat: idx for idx, cat in enumerate(categories)}

    records = balance_good_samples(records, config.good_ratio, rng)

    clear_output_dirs(config.output_root)
    prepare_output_dirs(config.output_root)
    summary = process_records(records, config, rng, class_to_id)
    write_runtime_config(config, summary, categories)
    print(
        "Processed "
        f"{summary['processed']} samples "
        f"({summary['augmented']} augmented) into {config.output_root}"
    )
    return 0


def load_manifest(manifest_path: Path) -> list[ManifestRecord]:
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    if manifest_path.suffix.lower() == ".json":
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return [ManifestRecord(**item) for item in payload]

    if manifest_path.suffix.lower() == ".csv":
        with manifest_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return [ManifestRecord(**row) for row in reader]

    raise SystemExit(f"Unsupported manifest format: {manifest_path.suffix}")


def prepare_output_dirs(output_root: Path) -> None:
    for folder in ["images", "masks", "labels", "meta"]:
        (output_root / folder).mkdir(parents=True, exist_ok=True)


def clear_output_dirs(output_root: Path) -> None:
    for folder in ["images", "masks", "labels", "meta"]:
        folder_path = output_root / folder
        if folder_path.exists():
            shutil.rmtree(folder_path)


def balance_good_samples(
    records: list[ManifestRecord],
    good_ratio: float,
    rng: random.Random,
) -> list[ManifestRecord]:
    """Downsample 'good' samples so they don't overwhelm defect samples.

    For each (class_name, split) group, keep at most
    ``max(1, int(defect_count * good_ratio))`` good samples.
    Setting ``good_ratio`` to -1 disables filtering and keeps all samples.
    """
    if good_ratio < 0:
        return records

    from collections import defaultdict

    # Group records by (class_name, split)
    groups: dict[tuple[str, str], dict[str, list[ManifestRecord]]] = defaultdict(
        lambda: {"good": [], "defect": []}
    )
    for r in records:
        groups[(r.class_name, r.split)][r.label].append(r)

    balanced: list[ManifestRecord] = []
    total_good_before = 0
    total_good_after = 0

    for (class_name, split), labels in sorted(groups.items()):
        defect_records = labels["defect"]
        good_records = labels["good"]

        balanced.extend(defect_records)

        if not good_records:
            continue

        if split != "train":
            balanced.extend(good_records)
            total_good_after += len(good_records)
            total_good_before += len(good_records)
            continue

        total_good_before += len(good_records)
        max_good = max(1, int(len(defect_records) * good_ratio))
        if len(good_records) <= max_good:
            balanced.extend(good_records)
            total_good_after += len(good_records)
        else:
            sampled = rng.sample(good_records, max_good)
            balanced.extend(sampled)
            total_good_after += max_good

    print(
        f"Balance: kept {total_good_after}/{total_good_before} good samples "
        f"(good_ratio={good_ratio} in train split)"
    )
    return balanced


def process_records(
    records: Iterable[ManifestRecord],
    config: PreprocessConfig,
    rng: random.Random,
    class_to_id: dict[str, int],
) -> dict[str, int]:
    summary = {
        "processed": 0,
        "augmented": 0,
        "skipped": 0,
        "skipped_missing_or_empty_defect_mask": 0,
        "skipped_mask_size_mismatch": 0,
    }
    for record in records:
        image_path = resolve_source_path(config.dataset_root, record.image_path)
        mask_path = resolve_source_path(config.dataset_root, record.mask_path) if record.mask_path else None

        image = load_rgb_image(image_path)
        mask = load_mask_image(mask_path, image.size)

        if mask.size != image.size:
            summary["skipped"] += 1
            summary["skipped_mask_size_mismatch"] += 1
            continue

        if record.label == "defect" and not mask_has_foreground(mask):
            summary["skipped"] += 1
            summary["skipped_missing_or_empty_defect_mask"] += 1
            continue

        class_id = class_to_id[record.class_name]
        write_sample(record, image, mask, config.output_root, suffix="", class_id=class_id)
        summary["processed"] += 1

        if record.label == "defect" and config.augment_count > 0:
            for index in range(config.augment_count):
                aug_image, aug_mask = augment_pair(image, mask, rng)
                suffix = f"_aug{index + 1:02d}"
                write_sample(record, aug_image, aug_mask, config.output_root, suffix=suffix, class_id=class_id)
                summary["augmented"] += 1

    return summary


def resolve_source_path(dataset_root: Path, stored_path: str) -> Path:
    candidate = Path(stored_path)
    if candidate.is_absolute() and candidate.exists():
        return candidate

    normalized = Path(*candidate.parts)
    parts_lower = [part.lower() for part in normalized.parts]
    dataset_name_lower = dataset_root.name.lower()

    normalized_candidates: list[Path] = [normalized]
    if parts_lower and parts_lower[0] == dataset_name_lower:
        normalized_candidates.append(Path(*normalized.parts[1:]))

    if dataset_name_lower in parts_lower:
        idx = parts_lower.index(dataset_name_lower)
        if idx + 1 < len(normalized.parts):
            normalized_candidates.append(Path(*normalized.parts[idx + 1 :]))

    raw_index = next((i for i, part in enumerate(parts_lower) if part == "raw"), -1)
    if raw_index >= 0 and raw_index + 1 < len(normalized.parts):
        normalized_candidates.append(Path(*normalized.parts[raw_index + 1 :]))

    for item in normalized_candidates:
        direct = dataset_root / item
        if direct.exists():
            return direct

        raw_root = dataset_root / "raw"
        raw_candidate = raw_root / item
        if raw_candidate.exists():
            return raw_candidate

    raise FileNotFoundError(f"Could not resolve source path: {stored_path}")


def load_rgb_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def load_mask_image(path: Path | None, image_size: tuple[int, int]) -> Image.Image:
    if path is None or not path.exists():
        return Image.new("L", image_size, color=0)
    return Image.open(path).convert("L")


def augment_pair(image: Image.Image, mask: Image.Image, rng: random.Random) -> tuple[Image.Image, Image.Image]:
    if rng.random() < 0.5:
        image = ImageOps.mirror(image)
        mask = ImageOps.mirror(mask)

    if rng.random() < 0.1:
        image = ImageOps.flip(image)
        mask = ImageOps.flip(mask)

    angle = rng.uniform(-5.0, 5.0)
    image = image.rotate(angle, resample=Image.Resampling.BILINEAR, expand=False, fillcolor=(114, 114, 114))
    mask = mask.rotate(angle, resample=Image.Resampling.NEAREST, expand=False, fillcolor=0)

    image = apply_intensity_jitter(image, rng)
    return image, mask


def apply_intensity_jitter(image: Image.Image, rng: random.Random) -> Image.Image:
    brightness = 1.0 + rng.uniform(-0.08, 0.08)
    contrast = 1.0 + rng.uniform(-0.08, 0.08)
    image = ImageEnhance.Brightness(image).enhance(brightness)
    image = ImageEnhance.Contrast(image).enhance(contrast)
    return image


def mask_has_foreground(mask: Image.Image) -> bool:
    return bool(np.asarray(mask.convert("L"), dtype=np.uint8).max())


def write_sample(
    record: ManifestRecord,
    image: Image.Image,
    mask: Image.Image,
    output_root: Path,
    suffix: str,
    class_id: int,
) -> None:
    base_name = make_unique_sample_name(record, suffix)
    image_dir = output_root / "images" / record.split / record.class_name
    mask_dir = output_root / "masks" / record.split / record.class_name
    label_dir = output_root / "labels" / record.split / record.class_name
    image_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    image_path = image_dir / f"{base_name}.jpg"
    mask_path = mask_dir / f"{base_name}.png"
    label_path = label_dir / f"{base_name}.txt"

    image.save(image_path, quality=95)
    mask_binary = mask.convert("L").point(lambda value: 255 if value > 0 else 0)
    mask_binary.save(mask_path)
    label_path.write_text(mask_to_yolo_segmentation(mask_binary, class_id=class_id), encoding="utf-8")


def make_unique_sample_name(record: ManifestRecord, suffix: str) -> str:
    path = Path(record.image_path)
    source_stem = path.stem
    anomaly_type = path.parent.name
    orig_split = path.parent.parent.name
    return f"{orig_split}_{anomaly_type}__{source_stem}{suffix}"


def mask_to_yolo_segmentation(mask: Image.Image, class_id: int = 0) -> str:
    mask_array = np.asarray(mask.convert("L"), dtype=np.uint8)
    if mask_array.max() == 0:
        return ""

    contours = extract_contours(mask_array)
    if not contours:
        return ""

    lines: list[str] = []
    width = mask_array.shape[1]
    height = mask_array.shape[0]
    for contour in contours:
        if len(contour) < 3:
            continue
        points = normalize_contour(contour, width, height)
        if len(points) < 6:
            continue
        lines.append(str(class_id) + " " + " ".join(f"{value:.6f}" for value in points))
    return "\n".join(lines)


def extract_contours(mask_array: np.ndarray) -> list[np.ndarray]:
    try:
        import cv2

        contours, _ = cv2.findContours(mask_array, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return [contour.reshape(-1, 2) for contour in contours]
    except Exception:
        pass

    try:
        from skimage import measure

        contours = measure.find_contours(mask_array, 0.5)
        return [np.flip(contour, axis=1) for contour in contours]
    except Exception:
        return []


def normalize_contour(contour: np.ndarray, width: int, height: int) -> list[float]:
    points: list[float] = []
    for x, y in contour:
        points.append(float(np.clip(x / width, 0.0, 1.0)))
        points.append(float(np.clip(y / height, 0.0, 1.0)))
    return points


def write_runtime_config(config: PreprocessConfig, summary: dict[str, int], categories: list[str]) -> None:
    meta_dir = config.output_root / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_root": str(config.dataset_root.resolve()),
        "manifest_path": str(config.manifest_path.resolve()),
        "image_size": config.image_size,
        "preserve_original_size": True,
        "seed": config.seed,
        "augment_count": config.augment_count,
        "normalization": config.normalization,
        "save_augmented_train_only": config.save_augmented_train_only,
        "good_ratio": config.good_ratio,
        "categories": categories,
        "summary": summary,
        "normalization_stats": {
            "mode": config.normalization,
            "mean": IMAGENET_MEAN.tolist() if config.normalization == "imagenet" else [0.0, 0.0, 0.0],
            "std": IMAGENET_STD.tolist() if config.normalization == "imagenet" else [1.0, 1.0, 1.0],
        },
    }
    (meta_dir / "preprocess_config.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())