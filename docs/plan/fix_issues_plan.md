# Plan: Sửa lỗi & Bổ sung VQA Frontend

## Goal
Khắc phục các lỗi high/medium priority và bổ sung hiển thị VQA trên Frontend để hoàn thiện pipeline kiểm tra chất lượng.

---

## 1. Bug inspection_report.py: `max()` crash khi không có defect

### Input
- File `backend/services/inspection_report.py` line 93-95
- `position_counts` dict rỗng khi `enriched_predictions` = []

### Output
- Code không crash khi không có defect nào

### How to do
- Sửa ternary operator line 94-95 từ:
  ```python
  "most_affected_zone": max(position_counts, key=position_counts.get)
  if position_counts else "none",
  ```
  thành:
  ```python
  "most_affected_zone": max(position_counts, key=position_counts.get) if position_counts else "none",
  ```
  (Đưa `max()` vào trong nhánh `if position_counts` để tránh gọi `max()` trên dict rỗng)

---

## 2. Bug models.py: `utcnow()` deprecated trong Python 3.14

### Input
- File `backend/models.py` line 19
- `datetime.datetime.utcnow` bị deprecated từ Python 3.12+

### Output
- Không còn warning deprecated

### How to do
- Đổi `default=datetime.datetime.utcnow` thành `default=lambda: datetime.datetime.now(datetime.UTC)`

---

## 3. Bổ sung hiển thị VQA `vqa_quick_answers` trên Frontend

### Input
- File `frontend/index.html` function `displayResults()`
- Backend `/inspect` trả về `vqa_quick_answers` với 5 keys: defect, severity, verdict, position, count
- API client có method `askVQA()` nhưng chưa dùng

### Output
- Hiển thị `vqa_quick_answers` dưới dạng cards hỏi-đáp trong kết quả inspect
- Input form cho phép user nhập câu hỏi VQA tự do và gọi API `/vqa`

### How to do
1. **Hiển thị vqa_quick_answers**: Thêm section mới trong `displayResults()` (sau phần recommendations) với:
   - Tiêu đề "🤖 Hỏi & Đáp Về Ảnh"
   - Grid các card: mỗi card có icon + câu hỏi (tiếng Việt) + câu trả lời
   - Map key: {defect→"Có lỗi không?", severity→"Mức độ nghiêm trọng?", verdict→"Kết luận?", position→"Vị trí lỗi?", count→"Số lượng lỗi?"}

2. **Input VQA tự do**: Thêm form ở cuối kết quả với:
   - Input text + nút "Hỏi"
   - Gọi `apiClient.askVQA(file, question)` — cần lưu lại file/image reference
   - Hiển thị câu trả lời dưới dạng chat bubble

### Lưu ý
- Cần lưu file gốc (hoặc base64) để gửi lại API `/vqa` khi user hỏi
- Nếu không có vqa_quick_answers, ẩn section đi

---

## 4. Thiếu Pydantic schemas cho request/response validation

### Input
- Backend endpoints dùng raw dicts, không có validation

### Output
- Response có cấu trúc rõ ràng, tự động validate

### How to do
- Tạo file mới `backend/schemas.py` với các Pydantic models:
  - `Prediction(BaseModel)`: class_id, class_name, confidence, box, polygon (optional)
  - `EnrichedPrediction(Prediction)`: defect_type, area, position, size_classification, severity
  - `InspectResponse(BaseModel)`: status, filename, image_size, total_defects, predictions, result_image_url, report, vqa_quick_answers
  - `InspectionReport(BaseModel)`: inspection_summary, position_analysis, verdict, recommendations
- Gắn `response_model` vào các endpoint trong `main.py`

---

## 5. Testing thiếu

### Input
- Chỉ có 1 file test

### Output
- Test coverage cơ bản cho services

### How to do
- Tạo `backend/tests/test_feature_extraction.py`: test area, position, severity với mock predictions
- Tạo `backend/tests/test_inspection_report.py`: test verdict logic (PASS/FLAG/REJECT) với enriched predictions
- Tạo `backend/tests/test_api_basic.py`: test endpoint health check, test upload ảnh với mock

---

## 6. Video processing blocking `/process_video`

### Input
- Endpoint chạy đồng bộ, có thể timeout

### Output
- Response trả về ngay task ID, xử lý background

### How to do
- Tạo background task function `process_video_task(video_path, conf, max_frames, scene_threshold)`
- Endpoint `/process_video` gọi `BackgroundTasks.add_task(process_video_task, ...)` và trả về ngay `{"task_id": uuid, "status": "processing"}`
- Thêm endpoint `/task/{task_id}` để poll kết quả

---

## Lưu ý chung
- Mỗi thay đổi cần ghi log vào `THIGIACMAYTINH\log`
- Ưu tiên xử lý theo thứ tự: Bug 1 → Bug 2 → VQA FE → Schemas → Tests → Video