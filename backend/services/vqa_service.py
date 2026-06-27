from __future__ import annotations

from typing import Any

from PIL import Image


class VQAService:
    """
    Visual Question Answering Service.

    Supports three modes:
      1. Transformers VQA pipeline (dandelin/vilt-b32-finetuned-vqa)
      2. Context-aware rule-based (uses inspection report context)
      3. Legacy keyword-based fallback
    """

    def __init__(self):
        self.pipeline = None
        self.enabled = False
        try:
            from transformers import pipeline
            print("Attempting to load VQA model (dandelin/vilt-b32-finetuned-vqa)...")
            self.pipeline = pipeline("visual-question-answering", model="dandelin/vilt-b32-finetuned-vqa")
            self.enabled = True
            print("VQA model loaded successfully.")
        except Exception as e:
            print(f"VQA model loading skipped or failed (using fallback/mock): {e}")

    def answer_question(
        self,
        image: Image.Image,
        question: str,
        inspection_context: dict[str, Any] | None = None,
    ) -> str:
        """
        Answer a question about the image.

        Args:
            image: PIL Image to analyze
            question: Natural language question
            inspection_context: Optional enriched predictions + report context
                               from FeatureExtractor + InspectionReportService

        Returns:
            Answer string
        """
        # Mode 1: Use inspection context if available
        if inspection_context:
            context_answer = self._answer_with_context(question, inspection_context)
            if context_answer:
                return context_answer

        # Mode 2: Transformers VQA pipeline
        if self.enabled and self.pipeline is not None:
            try:
                results = self.pipeline(image, question)
                if results and len(results) > 0:
                    return results[0].get("answer", "I cannot answer this question.")
            except Exception as e:
                print(f"Error during VQA inference: {e}")

        # Mode 3: Legacy keyword-based fallback
        return self._keyword_fallback(question)

    # ──────────────────────────────────────────────────────────
    # Context-aware answering
    # ──────────────────────────────────────────────────────────

    def _answer_with_context(
        self,
        question: str,
        context: dict[str, Any],
    ) -> str | None:
        """Try to answer using the inspection report context."""
        q = question.lower()

        enriched = context.get("enriched_predictions", [])
        report = context.get("report", {})
        summary = report.get("inspection_summary", {})
        verdict = report.get("verdict", {})
        pos_analysis = report.get("position_analysis", {})

        total_defects = summary.get("total_defects_found", 0)
        verdict_result = verdict.get("result", "UNKNOWN")
        verdict_reason = verdict.get("reason", "")

        # "Is there any defect?" / "Any defect found?"
        if any(kw in q for kw in ["defect", "any defect", "found"]):
            if total_defects == 0:
                return "No defects detected. Product passes inspection."
            defect_types = summary.get("defect_type_breakdown", {})
            return (
                f"Yes, {total_defects} defect(s) found: {defect_types}. "
                f"Verdict: {verdict_result}."
            )

        # "What is the severity?" / "How severe?"
        if any(kw in q for kw in ["severity", "how severe", "how bad"]):
            sev = summary.get("severity_breakdown", {})
            return (
                f"Severity breakdown: {sev}. "
                f"Verdict: {verdict_result} - {verdict_reason}"
            )

        # "Where is the defect?" / "Position?"
        if any(kw in q for kw in ["where", "position", "location", "zone"]):
            zones = pos_analysis.get("defect_zones", {})
            if not zones:
                return "No defects found, so no position data available."
            most = pos_analysis.get("most_affected_zone", "unknown")
            return f"Defects located in zones: {zones}. Most affected zone: {most}."

        # "Pass or fail?" / "Verdict?"
        if any(kw in q for kw in ["verdict", "pass", "fail", "result", "qc", "quality"]):
            return f"Verdict: {verdict_result}. Reason: {verdict_reason}"

        # "How many defects?"
        if any(kw in q for kw in ["how many", "count", "number of"]):
            return f"Total defects found: {total_defects}."

        # "What type of defect?"
        if any(kw in q for kw in ["type", "kind", "what defect", "classification"]):
            if total_defects == 0:
                return "No defects detected."
            types = summary.get("defect_type_breakdown", {})
            return f"Defect types found: {types}."

        # "Recommendation?"
        if any(kw in q for kw in ["recommend", "what to do", "action", "suggestion"]):
            recs = report.get("recommendations", [])
            if recs:
                return "Recommendations: " + " ".join(recs)
            return "No specific recommendations."

        # "Report?" / "Summary?"
        if any(kw in q for kw in ["report", "summary", "overview"]):
            from backend.services.inspection_report import InspectionReportService
            reporter = InspectionReportService()
            if report:
                return reporter.generate_text_summary(report)
            return "No inspection report available."

        return None  # Let fallback handle

    # ──────────────────────────────────────────────────────────
    # Legacy keyword fallback
    # ──────────────────────────────────────────────────────────

    def _keyword_fallback(self, question: str) -> str:
        """Original keyword-based mock VQA."""
        q_lower = question.lower()
        if any(kw in q_lower for kw in ["defect", "fault", "error", "crack", "scratch", "dent", "damage"]):
            return "Based on visual analysis, a surface anomaly may be present. Please check /segment for mask validation."
        if "color" in q_lower:
            return "The object shows neutral gray and metallic textures typical of industrial surfaces."
        if "object" in q_lower or "what is" in q_lower or "product" in q_lower:
            return "An industrial component undergoing quality assurance inspection."
        if "good" in q_lower or "ok" in q_lower:
            return "The surface structure is overall intact, but micro-anomalies need verification."

        return "Visual inspection of the product shows fixed texture patterns. No obvious shape distortions."
