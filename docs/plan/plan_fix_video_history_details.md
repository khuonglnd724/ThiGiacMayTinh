# Plan: Fix Video & History - Thiếu chi tiết kiểm tra

## Goal
Khắc phục 2 vấn đề:
1. **Video results thiếu chi tiết**: Khi xử lý video, kết quả chỉ hiển thị frame gallery + defect log, không có enriched predictions (defect_type, area, position, severity, size), inspection report (verdict reason, recommendations), và VQA Q&A như khi inspect ảnh.
2. **History image mất chi tiết**: Khi xem lại lịch sử kiểm tra ảnh, chỉ còn ảnh + verdict badge, mất hết danh sách lỗi chi tiết (predictions), recommendations, VQA.

---

## 1. Video results thiếu Enriched Predictions + Report + VQA

### Input
- Endpoint `/process_video` (backend `main.py` line 336-469)
- Trả về raw predictions từ YOLOService (class_id, class_name, confidence, box, polygon)
- **Không chạy** FeatureExtraction, InspectionReportService, VQAService
- Frontend `renderVideoResultsOnly()` chỉ hiển thị frame gallery basic

### Output
- Video results hiển thị: enriched predictions + inspection report + VQA quick answers (giống `/inspect`)

### How to do
1. **Backend `main.py` - `/process_video` endpoint** (line 404-405):
   - Sau khi gọi `yolo_service.predict()`, thêm pipeline enrich cho mỗi frame:
     ```python
     from .services.feature_extraction import FeatureExtractor
     from .services.inspection_report import InspectionReportService
     
     extractor = FeatureExtractor()
     reporter = InspectionReportService()
     
     # Enrich predictions
     enriched = extractor.extract(predictions, frame_width, frame_height)
     
     # Generate report
     report = reporter.generate_report(enriched, filename=file.filename, image_size=(frame_width, frame_height))
     ```
   - **Lưu enriched predictions vào DB** thay vì raw predictions (sửa field `predictions` trong `InspectionLog`)
   - **Thêm field mới** vào `InspectionLog` model: `report` (JSON), `vqa_answers` (JSON) — hoặc lưu enriched predictions + report + VQA trong field `predictions` JSON
   - Trả về enriched predictions + report trong response logs

2. **Frontend `displayVideoResults()` / `renderVideoResultsOnly()`:**
   - Thêm section hiển thị defect details cards (giống `displayResults()` dòng 1018-1088)
   - Thêm section inspection report (verdict reason, recommendations)
   - Thêm section VQA quick answers (nếu có)
   - Format: mỗi frame có thể expand để xem chi tiết enriched predictions

3. **API Client `api.js` - `processVideo()`:**
   - Thêm tham số `enrich` (boolean) mặc định True
   - Gửi `enrich=true` lên backend

### Lưu ý
- Video có thể có nhiều frame → không nên enrich tất cả nếu quá nhiều
- Giới hạn: chỉ enrich 10 frame đầu tiên có defect, các frame khác giữ raw
- Cần tính frame_width, frame_height từ frame numpy array (frame.shape[1], frame.shape[0])

---

## 2. History image mất chi tiết khi restore

### Input
- Frontend `saveHistory()` (dòng 1255-1266) chỉ lưu: type, verdict, time, defects count, imageUrl
- Frontend `restoreImageResult()` (dòng 1518-1553) chỉ hiển thị: verdict badge, stats grid, result image
- **Không lưu** predictions, report, vqa_quick_answers vào localStorage

### Output
- Khi click history item, khôi phục đầy đủ: predictions cards, recommendations, VQA Q&A

### How to do
1. **Mở rộng `saveHistory()`** (dòng 1255-1266):
   - Lưu thêm `fullData` vào localStorage:
     ```javascript
     history.unshift({
       type: 'image',
       verdict: data.report?.verdict || 'UNKNOWN',
       time: new Date().toLocaleString('vi-VN'),
       defects: data.total_defects || 0,
       imageUrl: data.result_image_url || null,
       fullData: data  // Lưu toàn bộ response
     });
     ```
   - **Giới hạn**: Chỉ lưu tối đa 10 fullData để tránh quá tải localStorage (mỗi item ~50-100KB)

2. **Cập nhật `restoreImageResult()`** (dòng 1518-1553):
   - Kiểm tra nếu `item.fullData` tồn tại:
     ```javascript
     if (item.fullData) {
       displayResults(item.fullData);  // Gọi lại hàm render đầy đủ
       return;
     }
     ```
   - Nếu không có fullData (history cũ), giữ nguyên render cơ bản như hiện tại

3. **Load lịch sử hiệu quả**:
   - Khi loadHistory, hiển thị danh sách tóm tắt (verdict, time, count) như hiện tại
   - Chỉ load full data khi user click vào item

### Lưu ý
- localStorage giới hạn ~5-10MB → cần giới hạn số lượng `fullData`
- Nếu fullData quá lớn > 1MB, có thể skip lưu
- Cần xử lý trường hợp history cũ (không có fullData) vẫn hoạt động

---

## Thứ tự ưu tiên thực hiện

1. **Video enriched predictions**: Sửa backend `/process_video` chạy FeatureExtraction + InspectionReport
2. **Video frontend display**: Thêm defect detail cards + report + VQA vào renderVideoResultsOnly()
3. **History save full data**: Mở rộng saveHistory() lưu fullData
4. **History restore full data**: Cập nhật restoreImageResult() dùng displayResults()
5. **Test**: Kiểm tra cả 2 luồng (video + image history)

--- 

## Lưu ý chung
- Tuân thủ rule: ghi log vào `log/` sau mỗi thay đổi
- Đảm bảo không làm hỏng history cũ (backward compatibility)
- Video feature: không enrich tất cả frames (giới hạn 10 frame defect)