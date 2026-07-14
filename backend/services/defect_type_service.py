from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

try:
    from backend.config import get_defect_type_path
except ImportError:
    from config import get_defect_type_path

try:
    from AI.defect_type.model_utils import load_checkpoint, make_label_display, predict_pil, top_k_predictions
except ImportError:
    load_checkpoint = None  # type: ignore[assignment]
    make_label_display = None  # type: ignore[assignment]
    predict_pil = None  # type: ignore[assignment]
    top_k_predictions = None  # type: ignore[assignment]


class DefectTypeService:
    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self.model_path = Path(get_defect_type_path())
        self.model = None
        self.metadata = None

        if self.model_path.exists() and load_checkpoint is not None:
            try:
                self.model, self.metadata = load_checkpoint(self.model_path, device=self.device)
                print(f"Loaded defect-type classifier from: {self.model_path}")
            except Exception as exc:
                print(f"Failed to load defect-type classifier: {exc}")

    def predict(self, image: Image.Image | np.ndarray, detection: dict[str, Any] | None = None, top_k: int = 3) -> dict[str, Any]:
        if self.model is None or self.metadata is None or predict_pil is None:
            return {
                "label": "unknown",
                "defect_type": "unknown",
                "confidence": 0.0,
                "top_k": [],
            }

        pil_image = self._prepare_image(image)
        roi = self._extract_roi(pil_image, detection)
        prediction = predict_pil(self.model, roi, image_size=self.metadata.image_size, device=self.device)

        label_index = prediction["class_id"]
        label = self.metadata.label_names[label_index]
        defect_type = self._label_to_defect_type(label)
        top_predictions = []
        if top_k_predictions is not None:
            probs = np.asarray(prediction["probabilities"], dtype=np.float32)
            import torch

            top_predictions = top_k_predictions(torch.tensor(probs), self.metadata.label_names, top_k=top_k)
            for item in top_predictions:
                item["defect_type"] = self._label_to_defect_type(item["label"])

        return {
            "label": label,
            "defect_type": defect_type,
            "confidence": prediction["confidence"],
            "top_k": top_predictions,
        }

    def _prepare_image(self, image: Image.Image | np.ndarray) -> Image.Image:
        if isinstance(image, Image.Image):
            return image.convert("RGB")
        if image.ndim == 2:
            return Image.fromarray(image.astype(np.uint8), mode="L").convert("RGB")
        if image.shape[-1] == 3:
            return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        return Image.fromarray(image.astype(np.uint8)).convert("RGB")

    def _extract_roi(self, image: Image.Image, detection: dict[str, Any] | None) -> Image.Image:
        if not detection:
            return image

        width, height = image.size
        box = detection.get("box")
        polygon = detection.get("polygon")

        if box and len(box) == 4:
            x1, y1, x2, y2 = box
            return self._crop_box(image, x1, y1, x2, y2, width, height)

        if polygon and len(polygon) >= 3:
            xs = [point[0] for point in polygon]
            ys = [point[1] for point in polygon]
            return self._crop_box(image, min(xs) * width, min(ys) * height, max(xs) * width, max(ys) * height, width, height)

        return image

    def _crop_box(self, image: Image.Image, x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> Image.Image:
        left = max(0, int(math.floor(x1 - 0.15 * (x2 - x1))))
        top = max(0, int(math.floor(y1 - 0.15 * (y2 - y1))))
        right = min(width, int(math.ceil(x2 + 0.15 * (x2 - x1))))
        bottom = min(height, int(math.ceil(y2 + 0.15 * (y2 - y1))))
        if right <= left or bottom <= top:
            return image
        return image.crop((left, top, right, bottom))

    def _label_to_defect_type(self, label: str) -> str:
        if self.metadata is None:
            return label
        if self.metadata.taxonomy == "composite" and "__" in label:
            return label.split("__", 1)[1]
        return label
