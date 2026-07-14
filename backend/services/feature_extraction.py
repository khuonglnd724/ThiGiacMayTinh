"""
Module Trích Xuất Đặc Trưng
============================
Trích xuất các đặc trưng đã làm giàu từ kết quả dự đoán phân vùng YOLO:
  - Phân loại loại lỗi
  - Tính diện tích (pixel & chuẩn hóa)
  - Phân tích vị trí (vùng tương đối)
  - Phân loại kích thước (nhỏ/vừa/lớn)
  - Điểm mức độ nghiêm trọng (Thấp/Trung bình/Cao/Nghiêm trọng)
"""

from __future__ import annotations

import math
from typing import Any


# ──────────────────────────────────────────────
# Ánh xạ loại lỗi theo từng lớp sản phẩm
# ──────────────────────────────────────────────
PRODUCT_DEFECT_MAP: dict[str, list[str]] = {
    "bottle": ["scratch", "crack", "dent", "broken", "contamination"],
    "cable": ["missing_wire", "bent", "cracked_insulation", "scratch"],
    "capsule": ["scratch", "dent", "crack", "deformation"],
    "carpet": ["hole", "cut", "stain", "thread_error"],
    "grid": ["bent", "broken", "scratch", "missing_bar"],
    "hazelnut": ["crack", "hole", "scratch", "dent"],
    "leather": ["scratch", "cut", "stain", "fold"],
    "metal_nut": ["scratch", "dent", "bent", "crack", "rust"],
    "pill": ["scratch", "dent", "crack", "color_stain", "deformation"],
    "screw": ["scratch", "bent", "crack", "thread_defect"],
    "tile": ["crack", "chip", "stain", "glaze_defect"],
    "toothbrush": ["bristle_defect", "scratch", "deformation"],
    "transistor": ["bent_lead", "crack", "missing_part", "scratch"],
    "wood": ["scratch", "stain", "crack", "knot_defect"],
    "zipper": ["broken_tooth", "scratch", "bent", "missing_tooth"],
    "defect": ["surface_anomaly", "scratch", "crack", "dent", "contamination"],
}

FALLBACK_DEFECT_TYPES = ["surface_anomaly", "scratch", "crack", "dent", "contamination"]


# ── Vùng vị trí ────────────────────────────
POSITION_ZONES = {
    "top-left":      (0.0, 0.33, 0.0, 0.33),
    "top-center":    (0.33, 0.66, 0.0, 0.33),
    "top-right":     (0.66, 1.0, 0.0, 0.33),
    "middle-left":   (0.0, 0.33, 0.33, 0.66),
    "center":        (0.33, 0.66, 0.33, 0.66),
    "middle-right":  (0.66, 1.0, 0.33, 0.66),
    "bottom-left":   (0.0, 0.33, 0.66, 1.0),
    "bottom-center": (0.33, 0.66, 0.66, 1.0),
    "bottom-right":  (0.66, 1.0, 0.66, 1.0),
}


class FeatureExtractor:
    """
    Trích xuất các đặc trưng đã làm giàu từ kết quả dự đoán phân vùng YOLO.

    Cách dùng:
        extractor = FeatureExtractor()
        enriched = extractor.extract(predictions, img_width, img_height)
    """

    def __init__(self):
        pass

    def extract(
        self,
        predictions: list[dict[str, Any]],
        img_width: int,
        img_height: int,
    ) -> list[dict[str, Any]]:
        """
        Làm giàu các dự đoán thô với trích xuất đặc trưng.

        Args:
            predictions: Danh sách dự đoán thô từ YOLOService
            img_width: Chiều rộng ảnh gốc (px)
            img_height: Chiều cao ảnh gốc (px)

        Returns:
            Danh sách dự đoán đã làm giàu với:
                - defect_type, area (px, %), position, size_class, severity
        """
        enriched: list[dict[str, Any]] = []
        total_img_area = img_width * img_height

        for pred in predictions:
            item = dict(pred)  # shallow copy

            # ── 1. Loại lỗi ─────────────────────────────────
            item["defect_type"] = self._classify_defect_type(pred)

            # ── 2. Diện tích (diện tích đa giác + diện tích bbox) ─────────────
            polygon_area_norm, bbox_area_norm = self._compute_area(pred)
            polygon_area_px = polygon_area_norm * total_img_area
            bbox_area_px = bbox_area_norm * total_img_area

            item["area"] = {
                "polygon_area_px": round(polygon_area_px, 2),
                "polygon_area_norm": round(polygon_area_norm, 6),
                "polygon_area_percent": round(polygon_area_norm * 100, 4),
                "bbox_area_px": round(bbox_area_px, 2),
                "bbox_area_norm": round(bbox_area_norm, 6),
                "bbox_area_percent": round(bbox_area_norm * 100, 4),
            }

            # ── 3. Vị trí ────────────────────────────────────
            cx, cy = self._compute_centroid(pred)
            zone = self._classify_position(cx, cy)
            item["position"] = {
                "centroid_x_norm": round(cx, 4),
                "centroid_y_norm": round(cy, 4),
                "centroid_x_px": round(cx * img_width, 2),
                "centroid_y_px": round(cy * img_height, 2),
                "zone": zone,
                "zone_description": self._zone_description(zone),
            }

            # ── 4. Phân loại kích thước ─────────────────────────
            item["size_classification"] = self._classify_size(polygon_area_norm)

            # ── 5. Điểm mức độ nghiêm trọng ────────────────────────────
            severity = self._compute_severity(
                polygon_area_norm=polygon_area_norm,
                cy=cy,
                confidence=pred.get("confidence", 0.5),
                zone=zone,
            )
            item["severity"] = severity

            enriched.append(item)

        return enriched

    # ──────────────────────────────────────────────────────────
    # Các hàm hỗ trợ nội bộ
    # ──────────────────────────────────────────────────────────

    def _classify_defect_type(self, pred: dict[str, Any]) -> str:
        """Ánh xạ dự đoán thành loại lỗi dựa trên tên lớp & hình dạng mặt nạ."""
        class_name = pred.get("class_name", "defect").lower()
        possible_types = PRODUCT_DEFECT_MAP.get(class_name, FALLBACK_DEFECT_TYPES)

        polygon = pred.get("polygon")
        if polygon and len(polygon) >= 3:
            aspect = self._polygon_aspect_ratio(polygon)
            # Hình dạng kéo dài → scratch / crack / cut
            if aspect > 3.0:
                for t in possible_types:
                    if t in ("scratch", "crack", "cut", "thread_defect",
                             "broken_tooth", "missing_wire"):
                        return t
                return possible_types[0]
            # Hình dạng nhỏ gọn → dent / hole / chip
            if aspect < 1.5:
                for t in possible_types:
                    if t in ("dent", "hole", "chip", "stain"):
                        return t
                return possible_types[0]

        return possible_types[0]

    def _compute_area(self, pred: dict[str, Any]) -> tuple[float, float]:
        """
        Trả về (diện_tích_đa_giác_đã_chuẩn_hóa, diện_tích_bbox_đã_chuẩn_hóa).
        Cả hai đều trong khoảng [0, 1] so với toàn bộ ảnh.
        """
        # ── Diện tích đa giác qua công thức Shoelace ──
        polygon = pred.get("polygon")
        poly_area = 0.0
        if polygon and len(polygon) >= 3:
            xs = [p[0] for p in polygon]
            ys = [p[1] for p in polygon]
            n = len(xs)
            shoelace = 0.0
            for i in range(n):
                j = (i + 1) % n
                shoelace += xs[i] * ys[j]
                shoelace -= xs[j] * ys[i]
            poly_area = abs(shoelace) / 2.0
            poly_area = max(0.0, min(poly_area, 1.0))

        # ── Diện tích bounding box ──
        box = pred.get("box")
        bbox_area = 0.0
        if box and len(box) == 4:
            bx1, by1, bx2, by2 = box
            bbox_area = (bx2 - bx1) * (by2 - by1)
            bbox_area = max(0.0, min(bbox_area, 1.0))

        return poly_area, bbox_area

    def _compute_centroid(self, pred: dict[str, Any]) -> tuple[float, float]:
        """Trả về (cx_norm, cy_norm) trong [0, 1]."""
        polygon = pred.get("polygon")
        if polygon and len(polygon) >= 3:
            xs = [p[0] for p in polygon]
            ys = [p[1] for p in polygon]
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            return max(0.0, min(cx, 1.0)), max(0.0, min(cy, 1.0))

        # Dự phòng: tâm bounding box
        box = pred.get("box")
        if box and len(box) == 4:
            cx = (box[0] + box[2]) / 2.0
            cy = (box[1] + box[3]) / 2.0
            return max(0.0, min(cx, 1.0)), max(0.0, min(cy, 1.0))

        return 0.5, 0.5

    def _classify_position(self, cx: float, cy: float) -> str:
        """Khớp tâm với 1 trong 9 vùng vị trí."""
        for zone, (x1, x2, y1, y2) in POSITION_ZONES.items():
            if x1 <= cx < x2 and y1 <= cy < y2:
                return zone
        return "center"

    def _zone_description(self, zone: str) -> str:
        descriptions = {
            "top-left":      "Góc trên bên trái của bề mặt sản phẩm",
            "top-center":    "Cạnh trên / vùng trung tâm phía trên",
            "top-right":     "Góc trên bên phải của bề mặt sản phẩm",
            "middle-left":   "Phía trái / vùng giữa bên trái",
            "center":        "Vùng trung tâm của bề mặt sản phẩm",
            "middle-right":  "Phía phải / vùng giữa bên phải",
            "bottom-left":   "Góc dưới bên trái của bề mặt sản phẩm",
            "bottom-center": "Cạnh dưới / vùng trung tâm phía dưới",
            "bottom-right":  "Góc dưới bên phải của bề mặt sản phẩm",
        }
        return descriptions.get(zone, "Vị trí không xác định")

    def _classify_size(self, area_norm: float) -> dict[str, Any]:
        """Phân loại kích thước lỗi tương đối so với ảnh."""
        if area_norm < 0.001:
            level = "micro"
            desc = "Lỗi siêu nhỏ, khó thấy (< 0.1% bề mặt)"
        elif area_norm < 0.005:
            level = "tiny"
            desc = "Lỗi rất nhỏ (0.1% ~ 0.5% bề mặt)"
        elif area_norm < 0.02:
            level = "small"
            desc = "Lỗi nhỏ (0.5% ~ 2% bề mặt)"
        elif area_norm < 0.06:
            level = "medium"
            desc = "Lỗi trung bình (2% ~ 6% bề mặt)"
        elif area_norm < 0.15:
            level = "large"
            desc = "Lỗi lớn (6% ~ 15% bề mặt)"
        else:
            level = "critical"
            desc = "Kích thước lỗi nghiêm trọng (> 15% bề mặt)"

        return {
            "level": level,
            "description": desc,
            "area_percent": round(area_norm * 100, 4),
        }

    def _compute_severity(
        self,
        polygon_area_norm: float,
        cy: float,
        confidence: float,
        zone: str,
    ) -> dict[str, Any]:
        """
        Tính điểm mức độ nghiêm trọng (0-100) và cấp độ.

        Chấm điểm:
          - Đóng góp diện tích (0-40): diện tích lớn hơn -> điểm cao hơn
          - Đóng góp vị trí (0-30): vùng trung tâm/cạnh được tính trọng số
          - Đóng góp độ tin cậy (0-30): độ tin cậy cao hơn -> điểm cao hơn
        """
        # Điểm diện tích (0-40)
        area_score = 40.0 * (1.0 - math.exp(-polygon_area_norm * 50))

        # Điểm vị trí (0-30)
        center_zones = {"center", "top-center", "bottom-center"}
        edge_zones = {"top-left", "top-right", "bottom-left", "bottom-right"}
        if zone in center_zones:
            pos_score = 30.0
        elif zone in edge_zones:
            pos_score = 10.0
        else:
            pos_score = 20.0

        # Điểm độ tin cậy (0-30)
        conf_score = 30.0 * confidence

        total = area_score + pos_score + conf_score
        total = max(0.0, min(total, 100.0))

        # Cấp độ mức độ nghiêm trọng
        if total < 25:
            level = "Low"
            recommendation = "Chỉ theo dõi. Không cần hành động ngay."
        elif total < 50:
            level = "Medium"
            recommendation = "Đánh dấu để kiểm tra phụ. Có nguy cơ về chất lượng."
        elif total < 75:
            level = "High"
            recommendation = "Cần xem xét. Có khả năng là lỗi sản phẩm."
        else:
            level = "Critical"
            recommendation = "Khuyến cáo loại bỏ ngay. Lỗi sản phẩm nghiêm trọng."

        return {
            "score": round(total, 2),
            "level": level,
            "recommendation": recommendation,
            "details": {
                "area_contribution": round(area_score, 2),
                "position_contribution": round(pos_score, 2),
                "confidence_contribution": round(conf_score, 2),
            },
        }

    @staticmethod
    def _polygon_aspect_ratio(polygon: list[list[float]]) -> float:
        """Tính tỷ lệ chiều rộng/chiều cao của bounding box đa giác."""
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        if h < 1e-8:
            return 999.0
        return w / h