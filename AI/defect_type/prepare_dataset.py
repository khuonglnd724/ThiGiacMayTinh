from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from AI.defect_type.dataset import collect_label_names, discover_defect_samples, crop_roi_with_mask, split_samples_by_label
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare ROI crops for the defect-type classifier.")
    parser.add_argument("--preprocess-root", default="AI/preprocess/output", help="Root of the existing preprocessing output.")
    parser.add_argument("--output-root", default="AI/defect_type/output", help="Destination root for prepared crops and metadata.")
    parser.add_argument("--taxonomy", choices=["composite", "global"], default="composite", help="Label strategy for the second-stage classifier.")
    parser.add_argument("--split", choices=["train", "val", "test"], default=None, help="Optional split filter.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for quick inspection.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    preprocess_root = Path(args.preprocess_root)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    samples = discover_defect_samples(preprocess_root, taxonomy=args.taxonomy, split=args.split)
    if args.limit > 0:
        samples = samples[: args.limit]

    split_result = split_samples_by_label(samples, seed=42)
    split_map = [("train", split_result.train), ("val", split_result.val), ("test", split_result.test)]
    label_names = collect_label_names(samples)
    crops_root = output_root / "crops"
    crops_root.mkdir(parents=True, exist_ok=True)

    manifest_path = output_root / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["split", "class_name", "defect_type", "label", "image_path", "mask_path", "crop_path", "source_name"],
        )
        writer.writeheader()

        for split_name, split_samples in split_map:
            for index, sample in enumerate(split_samples):
                crop_dir = crops_root / split_name / sample.label
                crop_dir.mkdir(parents=True, exist_ok=True)
                crop_path = crop_dir / f"{sample.class_name}_{sample.source_name}_{index:06d}.jpg"

                image = crop_roi_with_mask(image=Image.open(sample.image_path), mask=Image.open(sample.mask_path))
                image.save(crop_path, quality=95)

                writer.writerow(
                    {
                        "split": split_name,
                        "class_name": sample.class_name,
                        "defect_type": sample.defect_type,
                        "label": sample.label,
                        "image_path": str(sample.image_path),
                        "mask_path": str(sample.mask_path),
                        "crop_path": str(crop_path),
                        "source_name": sample.source_name,
                    }
                )

    meta = {
        "preprocess_root": str(preprocess_root.resolve()),
        "taxonomy": args.taxonomy,
        "split": args.split,
        "sample_count": len(samples),
        "train_count": len(split_result.train),
        "val_count": len(split_result.val),
        "test_count": len(split_result.test),
        "labels": label_names,
    }
    (output_root / "dataset_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(samples)} ROI samples at {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
