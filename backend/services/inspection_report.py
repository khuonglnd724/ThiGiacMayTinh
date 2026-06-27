"""
Inspection Report Service
=========================
Generates structured inspection reports based on enriched predictions
from the Feature Extraction Module.

Uses rule-based logic to summarize defect findings and provide
quality control recommendations.
"""

from __future__ import annotations

from typing import Any


class InspectionReportService:
    """
    Generates a human-readable inspection report from enriched predictions.

    Usage:
        reporter = InspectionReportService()
        report = reporter.generate_report(enriched_predictions, filename, img_size)
    """

    def __init__(self):
        pass

    def generate_report(
        self,
        enriched_predictions: list[dict[str, Any]],
        filename: str = "unknown",
        image_size: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a full inspection report.

        Args:
            enriched_predictions: Output from FeatureExtractor.extract()
            filename: Original image/video filename
            image_size: (width, height) of original image

        Returns:
            Structured inspection report dict
        """
        total_defects = len(enriched_predictions)

        # Defect type breakdown
        defect_type_counts: dict[str, int] = {}
        for pred in enriched_predictions:
            dt = pred.get("defect_type", "unknown")
            defect_type_counts[dt] = defect_type_counts.get(dt, 0) + 1

        # Severity breakdown
        severity_counts: dict[str, int] = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
        for pred in enriched_predictions:
            sev = pred.get("severity", {}).get("level", "Low")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Position heatmap
        position_counts: dict[str, int] = {}
        for pred in enriched_predictions:
            zone = pred.get("position", {}).get("zone", "unknown")
            position_counts[zone] = position_counts.get(zone, 0) + 1

        # Overall verdict
        critical_or_high = severity_counts.get("Critical", 0) + severity_counts.get("High", 0)
        if critical_or_high > 0:
            verdict = "REJECT"
            verdict_reason = f"Found {critical_or_high} High/Critical severity defect(s). Product fails QC."
        elif total_defects == 0:
            verdict = "PASS"
            verdict_reason = "No defects detected. Product passes quality check."
        elif severity_counts.get("Medium", 0) > 2:
            verdict = "REJECT"
            verdict_reason = f"Multiple medium-severity defects ({severity_counts['Medium']}). Product fails QC."
        elif severity_counts.get("Medium", 0) > 0:
            verdict = "FLAG"
            verdict_reason = "Minor/medium defects found. Recommend secondary inspection."
        else:
            verdict = "PASS"
            verdict_reason = "Minor defects only within acceptable tolerance."

        # Build report
        report = {
            "inspection_summary": {
                "filename": filename,
                "image_size": f"{image_size[0]}x{image_size[1]}" if image_size else "unknown",
                "total_defects_found": total_defects,
                "defect_type_breakdown": defect_type_counts,
                "severity_breakdown": severity_counts,
            },
            "position_analysis": {
                "defect_zones": position_counts,
                "most_affected_zone": max(position_counts, key=position_counts.get)
                if position_counts else "none",
            },
            "verdict": {
                "result": verdict,
                "reason": verdict_reason,
                "action_required": verdict in ("REJECT", "FLAG"),
            },
            "recommendations": self._generate_recommendations(
                verdict, severity_counts, total_defects
            ),
            "defect_details": enriched_predictions,
        }

        return report



    def generate_text_summary(self, report: dict[str, Any]) -> str:
        """
        Generate a human-readable text summary from the report dict.
        Useful for VQA context or display.
        """
        summary = report.get("inspection_summary", {})
        verdict = report.get("verdict", {})

        lines = [
            f"Inspection Report for: {summary.get('filename', 'unknown')}",
            f"Image Size: {summary.get('image_size', 'unknown')}",
            f"Total Defects: {summary.get('total_defects_found', 0)}",
            f"Defect Types: {summary.get('defect_type_breakdown', {})}",
            f"Severity Breakdown: {summary.get('severity_breakdown', {})}",
            f"Verdict: {verdict.get('result', 'UNKNOWN')} - {verdict.get('reason', 'N/A')}",
        ]

        pos = report.get("position_analysis", {})
        if pos.get("most_affected_zone"):
            lines.append(f"Most Affected Zone: {pos['most_affected_zone']}")

        return "\n".join(lines)

    def _generate_recommendations(
        self,
        verdict: str,
        severity_counts: dict[str, int],
        total_defects: int,
    ) -> list[str]:
        """Generate actionable recommendations based on inspection results."""
        recs: list[str] = []

        if verdict == "REJECT":
            recs.append("Immediately quarantine rejected product.")
            if severity_counts.get("Critical", 0) > 0:
                recs.append("Notify quality engineering team for root cause analysis.")
            recs.append("Review production line parameters for anomalies.")

        elif verdict == "FLAG":
            recs.append("Route product to manual QC inspection station.")
            recs.append("Capture additional images for documentation.")
            if total_defects > 3:
                recs.append("Consider temporary line slowdown for quality check.")

        else:
            recs.append("Product passes QC. Proceed to packaging.")
            if total_defects > 0:
                recs.append("Log minor defects for statistical process control.")

        if total_defects == 0:
            recs.append("No action required.")

        return recs
