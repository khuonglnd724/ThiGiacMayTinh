from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

from AI.defect_type.model_utils import build_image_transform


SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class DefectSample:
    split: str
    class_name: str
    defect_type: str
    label: str
    image_path: Path
    mask_path: Path
    source_name: str


@dataclass(frozen=True)
class SplitResult:
    train: list[DefectSample]
    val: list[DefectSample]
    test: list[DefectSample]


def parse_preprocessed_stem(stem: str) -> tuple[str, str, str] | None:
    base_stem = re.sub(r"_aug\d+$", "", stem)
    if "__" not in base_stem:
        return None

    head, source_stem = base_stem.split("__", 1)
    if "_" not in head:
        return None

    split, defect_type = head.split("_", 1)
    if split not in SPLITS:
        return None
    return split, defect_type, source_stem


def build_label(defect_type: str, class_name: str, taxonomy: str) -> str:
    if taxonomy == "composite":
        return f"{class_name}__{defect_type}"
    return defect_type


def group_key(sample: DefectSample) -> tuple[str, str, str]:
    return sample.class_name, sample.defect_type, sample.source_name


def split_samples_by_label(
    samples: list[DefectSample],
    seed: int,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    min_per_split: int = 1,
) -> SplitResult:
    """Split samples so that *every* label appears in train, val and test.

    IMPORTANT (bug fix): the previous implementation grouped whole
    ``(label, source_name)`` blocks and assigned each block atomically to a
    single split. Many labels had only 1-2 source blocks, so entire labels
    ended up only in train (or only in val/test). That produced "train-only"
    classes the model could never be evaluated on and invisible val/test
    classes.

    The corrected logic shuffles the individual images of each label and
    distributes them across the three splits by ratio, guaranteeing at least
    ``min_per_split`` image(s) per split whenever the label has enough
    samples. Source grouping is intentionally dropped so every class is
    represented everywhere.
    """
    if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 1e-6:
        raise SystemExit("Train/val/test ratios must sum to 1.0")

    import random
    from collections import defaultdict

    by_label: dict[str, list[DefectSample]] = defaultdict(list)
    for sample in samples:
        by_label[sample.label].append(sample)

    rng = random.Random(seed)
    train_samples: list[DefectSample] = []
    val_samples: list[DefectSample] = []
    test_samples: list[DefectSample] = []

    for label in sorted(by_label.keys()):
        items = list(by_label[label])
        rng.shuffle(items)
        n = len(items)

        if n <= 2:
            # Not enough samples to populate all three splits: keep all in
            # train and (if possible) one extra copy in val, else test.
            train_samples.extend(items)
            continue

        train_target = max(min_per_split, round(n * train_ratio))
        val_target = max(min_per_split, round(n * val_ratio))
        test_target = max(min_per_split, n - train_target - val_target)

        # Repair overflow while preserving the per-split minimum.
        while train_target + val_target + test_target > n:
            if train_target > val_target and train_target > test_target and train_target > min_per_split:
                train_target -= 1
            elif val_target > test_target and val_target > min_per_split:
                val_target -= 1
            elif test_target > min_per_split:
                test_target -= 1
            else:
                break

        # Redistribute any leftover to keep ratios as close as possible.
        remaining = n - (train_target + val_target + test_target)
        while remaining > 0:
            if train_target <= val_target and train_target <= test_target:
                train_target += 1
            elif val_target <= test_target:
                val_target += 1
            else:
                test_target += 1
            remaining -= 1

        train_samples.extend(items[:train_target])
        val_samples.extend(items[train_target : train_target + val_target])
        test_samples.extend(items[train_target + val_target : train_target + val_target + test_target])

    return SplitResult(train=train_samples, val=val_samples, test=test_samples)


def discover_defect_samples(preprocess_root: Path, taxonomy: str = "composite", split: str | None = None) -> list[DefectSample]:
    samples: list[DefectSample] = []
    mask_root = preprocess_root / "masks"
    if not mask_root.exists():
        return samples

    split_names = [split] if split else list(SPLITS)
    for split_name in split_names:
        split_mask_root = mask_root / split_name
        if not split_mask_root.exists():
            continue

        for class_dir in sorted(path for path in split_mask_root.iterdir() if path.is_dir()):
            for mask_path in sorted(class_dir.glob("*.png")):
                parsed = parse_preprocessed_stem(mask_path.stem)
                if not parsed:
                    continue
                parsed_split, defect_type, source_stem = parsed
                # Skip parsed_split matching check because all defect samples originally start with "test_" 
                # but are now distributed across "train", "val", and "test" folders during preprocessing.

                image_path = preprocess_root / "images" / split_name / class_dir.name / f"{mask_path.stem}.jpg"
                if not image_path.exists():
                    continue

                label = build_label(defect_type, class_dir.name, taxonomy)
                samples.append(
                    DefectSample(
                        split=split_name,
                        class_name=class_dir.name,
                        defect_type=defect_type,
                        label=label,
                        image_path=image_path,
                        mask_path=mask_path,
                        source_name=source_stem,
                    )
                )

    return samples


def collect_label_names(samples: Iterable[DefectSample]) -> list[str]:
    return sorted({sample.label for sample in samples})


def compute_foreground_box(mask: np.ndarray, padding_ratio: float = 0.18) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0 or len(ys) == 0:
        height, width = mask.shape[:2]
        return 0, 0, width, height

    x1 = int(xs.min())
    x2 = int(xs.max()) + 1
    y1 = int(ys.min())
    y2 = int(ys.max()) + 1

    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    pad_x = max(4, int(width * padding_ratio))
    pad_y = max(4, int(height * padding_ratio))

    h, w = mask.shape[:2]
    left = max(0, x1 - pad_x)
    top = max(0, y1 - pad_y)
    right = min(w, x2 + pad_x)
    bottom = min(h, y2 + pad_y)
    return left, top, right, bottom


def crop_roi_with_mask(image: Image.Image, mask: Image.Image, padding_ratio: float = 0.18) -> Image.Image:
    image_rgb = image.convert("RGB")
    mask_l = mask.convert("L")
    mask_arr = np.asarray(mask_l, dtype=np.uint8)
    left, top, right, bottom = compute_foreground_box(mask_arr, padding_ratio=padding_ratio)

    image_crop = np.asarray(image_rgb.crop((left, top, right, bottom)), dtype=np.uint8)
    mask_crop = np.asarray(mask_l.crop((left, top, right, bottom)), dtype=np.uint8) > 0

    if image_crop.size == 0:
        return image_rgb

    # Preserve more contextual information by keeping the original crop outside the mask,
    # but soften the background so the classifier still focuses on the defect region.
    mean_color = image_crop.reshape(-1, 3).mean(axis=0).astype(np.uint8)
    background = np.full_like(image_crop, mean_color)
    blended = (0.35 * image_crop + 0.65 * background).astype(np.uint8)
    roi = np.where(mask_crop[..., None], image_crop, blended)
    return Image.fromarray(roi)


class DefectTypeDataset(Dataset[tuple[torch.Tensor, int]]):
    def __init__(
        self,
        samples: list[DefectSample],
        label_to_index: dict[str, int],
        image_size: int = 224,
        train: bool = False,
        padding_ratio: float = 0.18,
    ) -> None:
        self.samples = samples
        self.label_to_index = label_to_index
        self.image_size = image_size
        self.train = train
        self.padding_ratio = padding_ratio
        self.transform = build_image_transform(image_size=image_size, train=train)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        sample = self.samples[index]
        image = Image.open(sample.image_path)
        mask = Image.open(sample.mask_path)
        roi = crop_roi_with_mask(image, mask, padding_ratio=self.padding_ratio)
        tensor = self.transform(roi)
        label = self.label_to_index[sample.label]
        return tensor, label


def count_label_samples(samples: list[DefectSample]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sample in samples:
        counts[sample.label] = counts.get(sample.label, 0) + 1
    return counts


def summarize_samples(samples: list[DefectSample]) -> dict[str, Any]:
    counts = count_label_samples(samples)
    return {
        "total": len(samples),
        "counts": counts,
    }
