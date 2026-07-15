"""
Dịch Vụ Báo Cáo Kiểm Tra
=========================
Tạo báo cáo kiểm tra có cấu trúc dựa trên các dự đoán đã bổ sung thông tin
từ Module Trích Xuất Đặc Trưng.

Sử dụng logic dựa trên quy tắc để tổng hợp kết quả phát hiện lỗi và cung cấp
khuyến cáo kiểm soát chất lượng.
"""

from __future__ import annotations

from typing import Any


class InspectionReportService:
    """
    Tạo báo cáo kiểm tra có thể đọc được từ các dự đoán đã bổ sung thông tin.

    Cách dùng:
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
        Tạo báo cáo kiểm tra đầy đủ.

        Args:
            enriched_predictions: Kết quả từ FeatureExtractor.extract()
            filename: Tên file ảnh/video gốc
            image_size: (chiều rộng, chiều cao) của ảnh gốc

        Returns:
            Dict báo cáo kiểm tra có cấu trúc
        """
        total_defects = len(enriched_predictions)

        # Phân tích theo loại lỗi
        defect_type_counts: dict[str, int] = {}
        for pred in enriched_predictions:
            dt = pred.get("defect_type", "unknown")
            defect_type_counts[dt] = defect_type_counts.get(dt, 0) + 1

        # Phân tích theo mức độ nghiêm trọng
        severity_counts: dict[str, int] = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
        for pred in enriched_predictions:
            sev = pred.get("severity", {}).get("level", "Low")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Bản đồ nhiệt vị trí
        position_counts: dict[str, int] = {}
        for pred in enriched_predictions:
            zone = pred.get("position", {}).get("zone", "unknown")
            position_counts[zone] = position_counts.get(zone, 0) + 1

        # Kết luận tổng thể
        critical_or_high = severity_counts.get("Critical", 0) + severity_counts.get("High", 0)
        if critical_or_high > 0:
            verdict = "REJECT"
            verdict_reason = f"Phát hiện {critical_or_high} lỗi mức Cao/Nghiêm trọng. Sản phẩm không đạt QC."
        elif total_defects == 0:
            verdict = "PASS"
            verdict_reason = "Không phát hiện lỗi. Sản phẩm đạt tiêu chuẩn chất lượng."
        elif severity_counts.get("Medium", 0) > 2:
            verdict = "REJECT"
            verdict_reason = f"Nhiều lỗi mức trung bình ({severity_counts['Medium']}). Sản phẩm không đạt QC."
        elif severity_counts.get("Medium", 0) > 0:
            verdict = "FLAG"
            verdict_reason = "Phát hiện lỗi nhỏ/trung bình. Khuyến cáo kiểm tra phụ."
        else:
            verdict = "PASS"
            verdict_reason = "Chỉ có lỗi nhỏ trong phạm vi dung sai cho phép."

        # Xây dựng báo cáo
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
                "most_affected_zone": max(position_counts, key=position_counts.get) if position_counts else "none",
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
        Tạo tóm tắt văn bản có thể đọc được từ dict báo cáo.
        Hữu ích cho ngữ cảnh VQA hoặc hiển thị.
        """
        summary = report.get("inspection_summary", {})
        verdict = report.get("verdict", {})

        lines = [
            f"Báo cáo kiểm tra cho: {summary.get('filename', 'unknown')}",
            f"Kích thước ảnh: {summary.get('image_size', 'unknown')}",
            f"Tổng số lỗi: {summary.get('total_defects_found', 0)}",
            f"Loại lỗi: {summary.get('defect_type_breakdown', {})}",
            f"Phân bố mức độ: {summary.get('severity_breakdown', {})}",
            f"Kết luận: {verdict.get('result', 'UNKNOWN')} - {verdict.get('reason', 'N/A')}",
        ]

        pos = report.get("position_analysis", {})
        if pos.get("most_affected_zone"):
            lines.append(f"Vùng bị ảnh hưởng nhiều nhất: {pos['most_affected_zone']}")

        return "\n".join(lines)

    def _generate_recommendations(
        self,
        verdict: str,
        severity_counts: dict[str, int],
        total_defects: int,
    ) -> list[str]:
        """Tạo các khuyến cáo có thể thực hiện dựa trên kết quả kiểm tra."""
        recs: list[str] = []

        if verdict == "REJECT":
            recs.append("Cách ly ngay sản phẩm bị loại bỏ.")
            if severity_counts.get("Critical", 0) > 0:
                recs.append("Thông báo cho nhóm kỹ thuật chất lượng để phân tích nguyên nhân gốc rễ.")
            recs.append("Rà soát thông số dây chuyền sản xuất để tìm bất thường.")

        elif verdict == "FLAG":
            recs.append("Chuyển sản phẩm đến trạm kiểm tra QC thủ công.")
            recs.append("Chụp thêm ảnh để lưu trữ tài liệu.")
            if total_defects > 3:
                recs.append("Cân nhắc giảm tốc độ tạm thời để kiểm tra chất lượng.")

        else:
            recs.append("Sản phẩm đạt QC. Tiến hành đóng gói.")
            if total_defects > 0:
                recs.append("Ghi nhận lỗi nhỏ để kiểm soát quy trình thống kê.")

        if total_defects == 0:
            recs.append("Không cần hành động.")

        return recs