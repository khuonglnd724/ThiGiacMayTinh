"""
Feature Extraction Module
=========================
Extracts enriched features from YOLO segmentation predictions:
  - Defect type classification
  - Area calculation (pixel & normalized)
  - Position analysis (relative zones)
  - Size classification (small/medium/large)
  - Severity scoring (Low/Medium/High/Critical)
"""

from __future__ import annotations

import math
from typing import Any


# ──────────────────────────────────────────────
# Defect type mapping per product class
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


# ── Position zones ────────────────────────────
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
    Extracts enriched features from YOLO segmentation predictions.

    Usage:
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
        Enrich raw predictions with feature extraction.

        Args:
            predictions: List of raw predictions from YOLOService
            img_width: Original image width (px)
            img_height: Original image height (px)

        Returns:
            List of enriched predictions with:
                - defect_type, area (px, %), position, size_class, severity
        """
        enriched: list[dict[str, Any]] = []
        total_img_area = img_width * img_height

        for pred in predictions:
            item = dict(pred)  # shallow copy

            # ── 1. Defect type ─────────────────────────────────
            item["defect_type"] = self._classify_defect_type(pred)

            # ── 2. Area (polygon area + bbox area) ─────────────
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

            # ── 3. Position ────────────────────────────────────
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

            # ── 4. Size classification ─────────────────────────
            item["size_classification"] = self._classify_size(polygon_area_norm)

            # ── 5. Severity scoring ────────────────────────────
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
    # Internal helpers
    # ──────────────────────────────────────────────────────────

    def _classify_defect_type(self, pred: dict[str, Any]) -> str:
        """Map prediction to a defect type based on class name & mask shape."""
        class_name = pred.get("class_name", "defect").lower()
        possible_types = PRODUCT_DEFECT_MAP.get(class_name, FALLBACK_DEFECT_TYPES)

        polygon = pred.get("polygon")
        if polygon and len(polygon) >= 3:
            aspect = self._polygon_aspect_ratio(polygon)
            # Elongated shape → scratch / crack / cut
            if aspect > 3.0:
                for t in possible_types:
                    if t in ("scratch", "crack", "cut", "thread_defect",
                             "broken_tooth", "missing_wire"):
                        return t
                return possible_types[0]
            # Compact shape → dent / hole / chip
            if aspect < 1.5:
                for t in possible_types:
                    if t in ("dent", "hole", "chip", "stain"):
                        return t
                return possible_types[0]

        return possible_types[0]

    def _compute_area(self, pred: dict[str, Any]) -> tuple[float, float]:
        """
        Return (polygon_normalized_area, bbox_normalized_area).
        Both in [0, 1] range relative to the full image.
        """
        # ── Polygon area via Shoelace formula ──
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

        # ── Bounding box area ──
        box = pred.get("box")
        bbox_area = 0.0
        if box and len(box) == 4:
            bx1, by1, bx2, by2 = box
            bbox_area = (bx2 - bx1) * (by2 - by1)
            bbox_area = max(0.0, min(bbox_area, 1.0))

        return poly_area, bbox_area

    def _compute_centroid(self, pred: dict[str, Any]) -> tuple[float, float]:
        """Return (cx_norm, cy_norm) in [0, 1]."""
        polygon = pred.get("polygon")
        if polygon and len(polygon) >= 3:
            xs = [p[0] for p in polygon]
            ys = [p[1] for p in polygon]
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            return max(0.0, min(cx, 1.0)), max(0.0, min(cy, 1.0))

        # Fallback: bounding box center
        box = pred.get("box")
        if box and len(box) == 4:
            cx = (box[0] + box[2]) / 2.0
            cy = (box[1] + box[3]) / 2.0
            return max(0.0, min(cx, 1.0)), max(0.0, min(cy, 1.0))

        return 0.5, 0.5

    def _classify_position(self, cx: float, cy: float) -> str:
        """Match centroid to one of 9 position zones."""
        for zone, (x1, x2, y1, y2) in POSITION_ZONES.items():
            if x1 <= cx < x2 and y1 <= cy < y2:
                return zone
        return "center"

    def _zone_description(self, zone: str) -> str:
        descriptions = {
            "top-left":      "Upper-left corner of the product surface",
            "top-center":    "Upper edge / top center region",
            "top-right":     "Upper-right corner of the product surface",
            "middle-left":   "Left side / middle-left region",
            "center":        "Central region of the product surface",
            "middle-right":  "Right side / middle-right region",
            "bottom-left":   "Lower-left corner of the product surface",
            "bottom-center": "Bottom edge / lower center region",
            "bottom-right":  "Lower-right corner of the product surface",
        }
        return descriptions.get(zone, "Unknown position")

    def _classify_size(self, area_norm: float) -> dict[str, Any]:
        """Classify defect size relative to image."""
        if area_norm < 0.001:
            level = "micro"
            desc = "Micro defect, barely visible (< 0.1% of surface)"
        elif area_norm < 0.005:
            level = "tiny"
            desc = "Tiny defect (0.1% ~ 0.5% of surface)"
        elif area_norm < 0.02:
            level = "small"
            desc = "Small defect (0.5% ~ 2% of surface)"
        elif area_norm < 0.06:
            level = "medium"
            desc = "Medium defect (2% ~ 6% of surface)"
        elif area_norm < 0.15:
            level = "large"
            desc = "Large defect (6% ~ 15% of surface)"
        else:
            level = "critical"
            desc = "Critical defect size (> 15% of surface)"

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
        Compute severity score (0-100) and level.

        Scoring:
          - Area contribution (0-40): larger area -> higher score
          - Position contribution (0-30): center/edge zones weighted
          - Confidence contribution (0-30): higher conf -> higher score
        """
        # Area score (0-40)
        area_score = 40.0 * (1.0 - math.exp(-polygon_area_norm * 50))

        # Position score (0-30)
        center_zones = {"center", "top-center", "bottom-center"}
        edge_zones = {"top-left", "top-right", "bottom-left", "bottom-right"}
        if zone in center_zones:
            pos_score = 30.0
        elif zone in edge_zones:
            pos_score = 10.0
        else:
            pos_score = 20.0

        # Confidence score (0-30)
        conf_score = 30.0 * confidence

        total = area_score + pos_score + conf_score
        total = max(0.0, min(total, 100.0))

        # Severity level
        if total < 25:
            level = "Low"
            recommendation = "Monitor only. No immediate action required."
        elif total < 50:
            level = "Medium"
            recommendation = "Flag for secondary inspection. Potential quality concern."
        elif total < 75:
            level = "High"
            recommendation = "Requires review. Likely product defect."
        else:
            level = "Critical"
            recommendation = "Immediate rejection recommended. Severe product defect."

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
        """Compute width/height ratio of polygon bounding box."""
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        if h < 1e-8:
            return 999.0
        return w / h

