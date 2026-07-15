from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent))

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

# Ánh xạ lớp sản phẩm (cha) -> các loại lỗi HỢP LỆ được model huấn luyện cho lớp đó.
# Sinh tự động từ manifest của tập train (AI/defect_type/output/manifest.csv).
# Mục đích: chặn model 2 dự đoán một loại lỗi không tồn tại ở lớp sản phẩm tương ứng
# (ví dụ: bottle không bao giờ có "cable_swap" / "missing_wire").
_ALLOWED_MAP_PATH = Path(__file__).resolve().parent.parent.parent / "AI" / "defect_type" / "class_defect_allowed.json"


class DefectTypeService:
    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self.model_path = Path(get_defect_type_path())
        self.model = None
        self.metadata = None
        self.allowed_map = self._load_allowed_map()

        if self.model_path.exists() and load_checkpoint is not None:
            try:
                self.model, self.metadata = load_checkpoint(self.model_path, device=self.device)
                print(f"Loaded defect-type classifier from: {self.model_path}")
            except Exception as exc:
                print(f"Failed to load defect-type classifier: {exc}")

    @staticmethod
    def _load_allowed_map() -> dict[str, list[str]]:
        if _ALLOWED_MAP_PATH.exists():
            try:
                with open(_ALLOWED_MAP_PATH, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception as exc:
                print(f"Failed to load class->defect allowed map: {exc}")
        return {}

    def predict(self, image: Image.Image | np.ndarray, detection: dict[str, Any] | None = None, top_k: int = 3) -> dict[str, Any]:
        if self.model is None or self.metadata is None or predict_pil is None:
            return {
                "label": "unknown",
                "defect_type": "unknown",
                "confidence": 0.0,
                "top_k": [],
                "constrained": False,
            }

        class_name = None
        if detection:
            class_name = detection.get("class_name")
        allowed_labels = self._allowed_labels_for(class_name)

        pil_image = self._prepare_image(image)
        roi = self._extract_roi(pil_image, detection)
        prediction = predict_pil(self.model, roi, image_size=self.metadata.image_size, device=self.device)

        probs = np.asarray(prediction["probabilities"], dtype=np.float32)
        label_names = self.metadata.label_names

        # ── Ràng buộc theo lớp cha ──────────────────────────────
        # Nếu có danh sách loại lỗi hợp lệ, chỉ xét những label đó.
        # Điều này ngăn model trả về một loại lỗi không tồn tại ở lớp sản phẩm.
        constrained = bool(allowed_labels)
        if constrained:
            allowed_set = set(allowed_labels)
            candidate_indices = [
                i for i, name in enumerate(label_names) if name in allowed_set
            ]
            if candidate_indices:
                best_idx = max(candidate_indices, key=lambda i: probs[i])
                label = label_names[best_idx]
                confidence = float(probs[best_idx])
            else:
                # Không có label nào khớp (class lạ) -> fallback unconstrained
                constrained = False
                best_idx = int(np.argmax(probs))
                label = label_names[best_idx]
                confidence = float(probs[best_idx])
        else:
            best_idx = int(np.argmax(probs))
            label = label_names[best_idx]
            confidence = float(probs[best_idx])

        defect_type = self._label_to_defect_type(label)

        # ── Top-k chỉ trong các label hợp lệ ────────────────────
        top_predictions = []
        if top_k_predictions is not None:
            import torch

            if constrained:
                masked = torch.tensor(probs).clone()
                mask = torch.tensor(
                    [name in allowed_set for name in label_names], dtype=torch.bool
                )
                masked[~mask] = -1.0
                top_predictions = top_k_predictions(masked, label_names, top_k=top_k)
            else:
                top_predictions = top_k_predictions(torch.tensor(probs), label_names, top_k=top_k)
            for item in top_predictions:
                item["defect_type"] = self._label_to_defect_type(item["label"])

        return {
            "label": label,
            "defect_type": defect_type,
            "confidence": confidence,
            "top_k": top_predictions,
            "constrained": constrained,
            "class_name": class_name,
        }

    def _allowed_labels_for(self, class_name: str | None) -> list[str]:
        """Trả về danh sách loại lỗi hợp lệ cho lớp sản phẩm (cha).
        Nếu class_name None/không có trong map -> [] (không ràng buộc)."""
        if not class_name or not self.allowed_map:
            return []
        return list(self.allowed_map.get(class_name.lower(), []))

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
