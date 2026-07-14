from __future__ import annotations

from typing import Any

from PIL import Image


class VQAService:
    """
    Dịch Vụ Hỏi Đáp Trực Quan (VQA).

    Hỗ trợ ba chế độ:
      1. Pipeline VQA Transformers (dandelin/vilt-b32-finetuned-vqa)
      2. Dựa trên quy tắc có nhận biết ngữ cảnh (sử dụng ngữ cảnh báo cáo kiểm tra)
      3. Dự phòng dựa trên từ khóa cũ
    """

    def __init__(self):
        self.pipeline = None
        self.enabled = False
        try:
            from transformers import pipeline
            print("Đang tải mô hình VQA (dandelin/vilt-b32-finetuned-vqa)...")
            self.pipeline = pipeline("visual-question-answering", model="dandelin/vilt-b32-finetuned-vqa")
            self.enabled = True
            print("Mô hình VQA đã tải thành công.")
        except Exception as e:
            print(f"Tải mô hình VQA thất bại hoặc bị bỏ qua (dùng dự phòng/mock): {e}")

    def answer_question(
        self,
        image: Image.Image,
        question: str,
        inspection_context: dict[str, Any] | None = None,
    ) -> str:
        """
        Trả lời câu hỏi về ảnh.

        Args:
            image: Ảnh PIL cần phân tích
            question: Câu hỏi bằng ngôn ngữ tự nhiên
            inspection_context: Ngữ cảnh tùy chọn gồm dự đoán đã làm giàu + ngữ cảnh báo cáo
                               từ FeatureExtractor + InspectionReportService

        Returns:
            Chuỗi câu trả lời
        """
        # Chế độ 1: Sử dụng ngữ cảnh kiểm tra nếu có
        if inspection_context:
            context_answer = self._answer_with_context(question, inspection_context)
            if context_answer:
                return context_answer

        # Chế độ 2: Pipeline VQA Transformers
        if self.enabled and self.pipeline is not None:
            try:
                results = self.pipeline(image, question)
                if results and len(results) > 0:
                    return results[0].get("answer", "Tôi không thể trả lời câu hỏi này.")
            except Exception as e:
                print(f"Lỗi trong quá trình suy luận VQA: {e}")

        # Chế độ 3: Dự phòng dựa trên từ khóa
        return self._keyword_fallback(question)

    # ──────────────────────────────────────────────────────────
    # Trả lời có nhận biết ngữ cảnh
    # ──────────────────────────────────────────────────────────

    def _answer_with_context(
        self,
        question: str,
        context: dict[str, Any],
    ) -> str | None:
        """Thử trả lời bằng ngữ cảnh báo cáo kiểm tra."""
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

        # Phát hiện ngôn ngữ của câu hỏi
        vi_kws = ["lỗi", "không", "phát hiện", "đạt", "hỏng", "kết luận", "mức độ", "nghiêm trọng", 
                  "ở đâu", "vị trí", "khuyến cáo", "tóm tắt", "báo cáo", "bao nhiêu", "mấy", "sản phẩm",
                  "gì", "nào", "khu vực"]
        is_vi = any(kw in q for kw in vi_kws)

        # 1. Có lỗi không? / Defect presence
        if any(kw in q for kw in ["defect", "any defect", "found", "có lỗi không", "phát hiện lỗi", "bị lỗi", "anomal", "có vết"]):
            if total_defects == 0:
                return "Không phát hiện lỗi nào trên sản phẩm này. Sản phẩm đạt tiêu chuẩn chất lượng."
            defect_types = summary.get("defect_type_breakdown", {})
            if not defect_types and enriched:
                defect_types = {}
                for p in enriched:
                    dt = p.get("defect_type") or p.get("class_name") or "anomaly"
                    defect_types[dt] = defect_types.get(dt, 0) + 1
            return f"Có, phát hiện {total_defects} lỗi: {defect_types}. Kết luận kiểm tra: {verdict_result}."

        # 2. Mức độ nghiêm trọng? / Severity
        if any(kw in q for kw in ["severity", "how severe", "how bad", "mức độ", "nghiêm trọng", "nặng không", "mức"]):
            sev = summary.get("severity_breakdown", {})
            if not sev and enriched:
                sev = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
                for p in enriched:
                    level = p.get("severity", {}).get("level") if isinstance(p.get("severity"), dict) else p.get("severity") or "Low"
                    sev[level] = sev.get(level, 0) + 1
            return f"Thống kê mức độ nghiêm trọng: {sev}. Kết luận: {verdict_result} - {verdict_reason}."

        # 3. Ở đâu? Vị trí? / Position
        if any(kw in q for kw in ["where", "position", "location", "zone", "ở đâu", "vị trí", "nằm ở", "khu vực"]):
            zones = pos_analysis.get("defect_zones", {})
            if not zones and enriched:
                zones = {}
                for p in enriched:
                    z = p.get("position", {}).get("zone") if isinstance(p.get("position"), dict) else p.get("position") or "unknown"
                    zones[z] = zones.get(z, 0) + 1
            if not zones:
                return "Không phát hiện lỗi, nên không có thông tin vị trí."
            most = pos_analysis.get("most_affected_zone")
            if not most or most == "none":
                most = max(zones, key=zones.get) if zones else "unknown"
            return f"Các vết lỗi được phát hiện ở khu vực: {zones}. Vùng bị ảnh hưởng nhiều nhất: {most}."

        # 4. Kết quả? Kết luận? / Verdict
        if any(kw in q for kw in ["verdict", "pass", "fail", "result", "qc", "quality", "kết luận", "đạt", "hỏng", "kết quả", "loại"]):
            return f"Kết luận chất lượng: {verdict_result}. Lý do: {verdict_reason}."

        # 5. Bao nhiêu lỗi? / Count
        if any(kw in q for kw in ["how many", "count", "number of", "bao nhiêu", "mấy lỗi", "số lượng"]):
            return f"Tổng số lỗi phát hiện được: {total_defects}."

        # 6. Loại lỗi? / Type
        if any(kw in q for kw in ["type", "kind", "what defect", "classification", "loại lỗi", "dạng lỗi", "lỗi gì"]):
            if total_defects == 0:
                return "Không phát hiện lỗi."
            types = summary.get("defect_type_breakdown", {})
            if not types and enriched:
                types = {}
                for p in enriched:
                    dt = p.get("defect_type") or p.get("class_name") or "anomaly"
                    types[dt] = types.get(dt, 0) + 1
            return f"Các loại lỗi phát hiện được: {types}."

        # 7. Khuyến cáo? / Recommendation
        if any(kw in q for kw in ["recommend", "what to do", "action", "suggestion", "khuyến cáo", "xử lý", "đề xuất"]):
            recs = report.get("recommendations", [])
            if recs:
                return "Khuyến cáo xử lý QC: " + " ".join(recs)
            return "Không có khuyến cáo cụ thể."

        # 8. Báo cáo? Tóm tắt? / Summary
        if any(kw in q for kw in ["report", "summary", "overview", "báo cáo", "tóm tắt", "tổng quan"]):
            if report:
                defect_desc = f"{total_defects} lỗi" if total_defects > 0 else "không có lỗi"
                return f"Báo cáo QC cho ảnh {filename}: Kết luận {verdict_result} ({verdict_reason}). Phát hiện {defect_desc}."
            return "Không có báo cáo."

        return None  # Để dự phòng xử lý

    # ──────────────────────────────────────────────────────────
    # Dự phòng dựa trên từ khóa
    # ──────────────────────────────────────────────────────────

    def _keyword_fallback(self, question: str) -> str:
        """Dự phòng VQA dựa trên từ khóa gốc, được làm giàu với các mẫu tiếng Việt."""
        q_lower = question.lower()
        
        # 1. Lỗi / Hỏng / Defect
        defect_kws = ["defect", "fault", "error", "crack", "scratch", "dent", "damage", 
                      "lỗi", "hỏng", "nứt", "xước", "móp", "bọt khí", "dị vật", "vết"]
        if any(kw in q_lower for kw in defect_kws):
            return ("Dựa trên phân tích hình ảnh, có thể có bất thường hoặc lỗi bề mặt xuất hiện. "
                    "Vui lòng kiểm tra chi tiết phân vùng lỗi (segmentation mask) để xác thực.")
                    
        # 2. Màu sắc / Color
        color_kws = ["color", "màu", "sắc"]
        if any(kw in q_lower for kw in color_kws):
            return "Đối tượng có màu xám trung tính và kết cấu kim loại đặc trưng của các bề mặt công nghiệp."
            
        # 3. Cái gì / Sản phẩm / Object
        object_kws = ["object", "what is", "product", "sản phẩm", "vật thể", "cái gì", "đây là"]
        if any(kw in q_lower for kw in object_kws):
            return "Đây là một linh kiện/sản phẩm công nghiệp đang được tiến hành kiểm tra chất lượng (QC)."
            
        # 4. Đạt / Tốt / Good
        good_kws = ["good", "ok", "đạt", "tốt", "bình thường", "ổn"]
        if any(kw in q_lower for kw in good_kws):
            return "Cấu trúc bề mặt tổng thể nhìn chung còn nguyên vẹn, tuy nhiên cần kiểm tra kỹ các vùng nghi ngờ có vi lỗi."
            
        # 5. Vị trí / Ở đâu / Position
        position_kws = ["ở đâu", "vị trí", "nào", "where", "location", "position"]
        if any(kw in q_lower for kw in position_kws):
            return "Vị trí lỗi (nếu có) được đánh dấu bằng khung bao hoặc mặt nạ màu trên ảnh kết quả."

        return "Kết quả kiểm tra trực quan cho thấy sản phẩm có kết cấu bề mặt cố định. Không phát hiện biến dạng hình học rõ rệt."