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

        enriched = context.get("enriched_predictions") or context.get("predictions") or []
        report = context.get("report", {})
        summary = report.get("inspection_summary", {})
        verdict = report.get("verdict", {})
        pos_analysis = report.get("position_analysis", {})

        total_defects = summary.get("total_defects_found")
        if total_defects is None:
            total_defects = len(enriched)
            
        verdict_result = verdict.get("result", "UNKNOWN")
        verdict_reason = verdict.get("reason", "")
        filename = summary.get("filename", "sản phẩm")

        # Detect language of question
        vi_kws = ["lỗi", "không", "phát hiện", "đạt", "hỏng", "kết luận", "mức độ", "nghiêm trọng", 
                  "ở đâu", "vị trí", "khuyến cáo", "tóm tắt", "báo cáo", "bao nhiêu", "mấy", "sản phẩm",
                  "gì", "nào", "khu vực"]
        is_vi = any(kw in q for kw in vi_kws)

        # 1. Defect presence / Có lỗi không?
        if any(kw in q for kw in ["defect", "any defect", "found", "có lỗi không", "phát hiện lỗi", "bị lỗi", "anomal", "có vết"]):
            if total_defects == 0:
                return "Không phát hiện lỗi nào trên sản phẩm này. Sản phẩm đạt tiêu chuẩn chất lượng." if is_vi else "No defects detected. Product passes inspection."
            defect_types = summary.get("defect_type_breakdown", {})
            if not defect_types and enriched:
                defect_types = {}
                for p in enriched:
                    dt = p.get("defect_type") or p.get("class_name") or "anomaly"
                    defect_types[dt] = defect_types.get(dt, 0) + 1
            if is_vi:
                return f"Có, phát hiện {total_defects} lỗi: {defect_types}. Kết luận kiểm tra: {verdict_result}."
            else:
                return f"Yes, {total_defects} defect(s) found: {defect_types}. Verdict: {verdict_result}."

        # 2. Severity / Mức độ nghiêm trọng?
        if any(kw in q for kw in ["severity", "how severe", "how bad", "mức độ", "nghiêm trọng", "nặng không", "mức"]):
            sev = summary.get("severity_breakdown", {})
            if not sev and enriched:
                sev = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
                for p in enriched:
                    level = p.get("severity", {}).get("level") if isinstance(p.get("severity"), dict) else p.get("severity") or "Low"
                    sev[level] = sev.get(level, 0) + 1
            if is_vi:
                return f"Thống kê mức độ nghiêm trọng: {sev}. Kết luận: {verdict_result} - {verdict_reason}."
            else:
                return f"Severity breakdown: {sev}. Verdict: {verdict_result} - {verdict_reason}"

        # 3. Position / Ở đâu? Vị trí?
        if any(kw in q for kw in ["where", "position", "location", "zone", "ở đâu", "vị trí", "nằm ở", "khu vực"]):
            zones = pos_analysis.get("defect_zones", {})
            if not zones and enriched:
                zones = {}
                for p in enriched:
                    z = p.get("position", {}).get("zone") if isinstance(p.get("position"), dict) else p.get("position") or "unknown"
                    zones[z] = zones.get(z, 0) + 1
            if not zones:
                return "Không phát hiện lỗi, nên không có thông tin vị trí." if is_vi else "No defects found, so no position data available."
            most = pos_analysis.get("most_affected_zone")
            if not most or most == "none":
                most = max(zones, key=zones.get) if zones else "unknown"
            if is_vi:
                return f"Các vết lỗi được phát hiện ở khu vực: {zones}. Vùng bị ảnh hưởng nhiều nhất: {most}."
            else:
                return f"Defects located in zones: {zones}. Most affected zone: {most}."

        # 4. Verdict / Kết quả? Kết luận?
        if any(kw in q for kw in ["verdict", "pass", "fail", "result", "qc", "quality", "kết luận", "đạt", "hỏng", "kết quả", "loại"]):
            if is_vi:
                return f"Kết luận chất lượng: {verdict_result}. Lý do: {verdict_reason}."
            else:
                return f"Verdict: {verdict_result}. Reason: {verdict_reason}"

        # 5. Count / Bao nhiêu lỗi? Có mấy lỗi?
        if any(kw in q for kw in ["how many", "count", "number of", "bao nhiêu", "mấy lỗi", "số lượng"]):
            if is_vi:
                return f"Tổng số lỗi phát hiện được: {total_defects}."
            else:
                return f"Total defects found: {total_defects}."

        # 6. Type / Loại lỗi? Lỗi gì?
        if any(kw in q for kw in ["type", "kind", "what defect", "classification", "loại lỗi", "dạng lỗi", "lỗi gì"]):
            if total_defects == 0:
                return "Không phát hiện lỗi." if is_vi else "No defects detected."
            types = summary.get("defect_type_breakdown", {})
            if not types and enriched:
                types = {}
                for p in enriched:
                    dt = p.get("defect_type") or p.get("class_name") or "anomaly"
                    types[dt] = types.get(dt, 0) + 1
            if is_vi:
                return f"Các loại lỗi phát hiện được: {types}."
            else:
                return f"Defect types found: {types}."

        # 7. Recommendation / Khuyến cáo? Đề xuất?
        if any(kw in q for kw in ["recommend", "what to do", "action", "suggestion", "khuyến cáo", "xử lý", "đề xuất"]):
            recs = report.get("recommendations", [])
            if recs:
                if is_vi:
                    return "Khuyến cáo xử lý QC: " + " ".join(recs)
                else:
                    return "Recommendations: " + " ".join(recs)
            return "Không có khuyến cáo cụ thể." if is_vi else "No specific recommendations."

        # 8. Summary / Báo cáo? Tóm tắt?
        if any(kw in q for kw in ["report", "summary", "overview", "báo cáo", "tóm tắt", "tổng quan"]):
            if report:
                if is_vi:
                    defect_desc = f"{total_defects} lỗi" if total_defects > 0 else "không có lỗi"
                    return f"Báo cáo QC cho ảnh {filename}: Kết luận {verdict_result} ({verdict_reason}). Phát hiện {defect_desc}."
                else:
                    try:
                        from backend.services.inspection_report import InspectionReportService
                    except ImportError:
                        from services.inspection_report import InspectionReportService
                    reporter = InspectionReportService()
                    return reporter.generate_text_summary(report)
            return "Không có báo cáo." if is_vi else "No inspection report available."

        return None  # Let fallback handle

    # ──────────────────────────────────────────────────────────
    # Legacy keyword fallback
    # ──────────────────────────────────────────────────────────

    def _keyword_fallback(self, question: str) -> str:
        """Original keyword-based mock VQA, enriched with Vietnamese patterns."""
        q_lower = question.lower()
        
        # 1. Defect / Lỗi / Hỏng
        defect_kws = ["defect", "fault", "error", "crack", "scratch", "dent", "damage", 
                      "lỗi", "hỏng", "nứt", "xước", "móp", "bọt khí", "dị vật", "vết"]
        if any(kw in q_lower for kw in defect_kws):
            return ("Dựa trên phân tích hình ảnh, có thể có bất thường hoặc lỗi bề mặt xuất hiện. "
                    "Vui lòng kiểm tra chi tiết phân vùng lỗi (segmentation mask) để xác thực.")
                    
        # 2. Color / Màu sắc
        color_kws = ["color", "màu", "sắc"]
        if any(kw in q_lower for kw in color_kws):
            return "Đối tượng có màu xám trung tính và kết cấu kim loại đặc trưng của các bề mặt công nghiệp."
            
        # 3. Object / Cái gì / Sản phẩm
        object_kws = ["object", "what is", "product", "sản phẩm", "vật thể", "cái gì", "đây là"]
        if any(kw in q_lower for kw in object_kws):
            return "Đây là một linh kiện/sản phẩm công nghiệp đang được tiến hành kiểm tra chất lượng (QC)."
            
        # 4. Good / OK / Đạt / Tốt
        good_kws = ["good", "ok", "đạt", "tốt", "bình thường", "ổn"]
        if any(kw in q_lower for kw in good_kws):
            return "Cấu trúc bề mặt tổng thể nhìn chung còn nguyên vẹn, tuy nhiên cần kiểm tra kỹ các vùng nghi ngờ có vi lỗi."
            
        # 5. Position / Ở đâu / Vị trí
        position_kws = ["ở đâu", "vị trí", "nào", "where", "location", "position"]
        if any(kw in q_lower for kw in position_kws):
            return "Vị trí lỗi (nếu có) được đánh dấu bằng khung bao hoặc mặt nạ màu trên ảnh kết quả."

        return "Kết quả kiểm tra trực quan cho thấy sản phẩm có kết cấu bề mặt cố định. Không phát hiện biến dạng hình học rõ rệt."
