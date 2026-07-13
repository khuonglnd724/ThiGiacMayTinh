# Log sửa lỗi & bổ sung VQA Frontend

## 2026-07-12 14:15

### Bug 1: inspection_report.py - `max()` crash khi không có defect
- **File**: `backend/services/inspection_report.py`
- **Dòng**: 93-95
- **Vấn đề**: `max(position_counts, key=position_counts.get)` được gọi trước khi check `if position_counts`, crash khi dict rỗng
- **Sửa**: Đưa `max()` vào trong nhánh `if position_counts` của ternary operator

### Bug 2: models.py - `utcnow()` deprecated
- **File**: `backend/models.py`
- **Dòng**: 19
- **Vấn đề**: `datetime.datetime.utcnow` deprecated từ Python 3.12+
- **Sửa**: Đổi thành `lambda: datetime.datetime.now(datetime.UTC)`

### Bug 3: Frontend - Bổ sung hiển thị VQA
- **File**: `frontend/index.html`
- **Vấn đề**: `vqa_quick_answers` được destructure nhưng không render, không có form hỏi VQA tự do
- **Sửa**:
  - Thêm section hiển thị vqa_quick_answers dạng cards trong displayResults() (sau recommendations)
  - Thêm form input + nút "Hỏi" cho VQA tự do, gọi apiClient.askVQA()
  - Thêm hàm `askVQAQuestion()` xử lý gọi API và hiển thị kết quả dạng chat bubble
  - Thêm CSS cho VQA section: .vqa-grid, .vqa-card, .vqa-form, .vqa-input, .vqa-answer-box, .vqa-chat-question, .vqa-chat-answer, .vqa-loading, .vqa-error
  - Lưu selectedFile để gửi lại API /vqa khi user hỏi

## Kết quả
- ✅ Bug 1: Fixed - ternary operator sửa đúng, không còn crash khi position_counts rỗng
- ✅ Bug 2: Fixed - dùng `lambda: datetime.datetime.now(datetime.UTC)` thay `utcnow()`
- ✅ Bug 3: Fixed - VQA quick answers hiển thị dạng cards, form hỏi tự do hoạt động
- ⏳ Bug 4-6: Chưa thực hiện (Pydantic schemas, Tests, Video background)

---

## 2026-07-13 19:45

### Task 1: Frontend - Lưu video history khi xử lý video thành công
- **File**: `frontend/index.html` (dòng 773-775)
- **Sửa**: Gọi `saveVideoHistory(result)` ngay sau `renderVideoResultsOnly(result)` trong hàm `processSelectedVideo()`.

### Task 2: Frontend - Đảm bảo total_defects luôn là number trong displayResults
- **File**: `frontend/index.html` (dòng 892)
- **Sửa**: Đổi `const total_defects = data.total_defects || 0;` thành `const total_defects = (typeof data.total_defects === 'number') ? data.total_defects : 0;` để tránh lỗi hiển thị object.

### Task 3: Backend - Endpoint /vqa nhận thêm tham số context
- **File**: `backend/main.py` (dòng 8, 272-297)
- **Sửa**: Import `Optional` và `json`. Cập nhật endpoint `/vqa` nhận thêm `context: Optional[str] = Form(None)`. Parse JSON từ context và truyền vào `vqa_service.answer_question(img, question, inspection_context=context)`.

### Task 4: Backend - Cải thiện _keyword_fallback trong vqa_service.py
- **File**: `backend/services/vqa_service.py` (dòng 153-166)
- **Sửa**: Cải tiến hàm `_keyword_fallback()` hỗ trợ thêm các từ khóa tiếng Việt về lỗi, màu sắc, sản phẩm, trạng thái để chatbot trả lời tự nhiên và đa dạng hơn khi không có context.

### Task 5: Frontend - Gửi context trong VQA Free-form
- **File**: `frontend/index.html` (dòng 605, 873, 886)
- **Sửa**: Khai báo `window.lastInspectionData = null` toàn cục. Gán `window.lastInspectionData = data` khi gọi `displayResults(data)`. Truyền `window.lastInspectionData` khi gọi `apiClient.askVQA(...)` trong `askVQAQuestion()`.

---

## 2026-07-13 19:51

### Task: Cải thiện logic VQA Context-aware hỗ trợ tiếng Việt và map thuộc tính `predictions`
- **File**: `backend/services/vqa_service.py` (dòng 75-148)
- **Sửa**:
  - Map lại danh sách predictions: Hỗ trợ cả `predictions` (frontend trả về) lẫn `enriched_predictions` (dùng ở backend).
  - Thêm cờ `is_vi` để tự động phát hiện ngôn ngữ câu hỏi dựa trên sự hiện diện của các từ khóa tiếng Việt.
  - Hỗ trợ phản hồi thông tin phân tích QC bằng tiếng Việt cho các câu hỏi thuộc 8 chủ đề chính: Phát hiện lỗi, Mức độ nghiêm trọng, Vị trí lỗi, Kết quả kiểm định, Số lượng lỗi, Loại lỗi, Khuyến cáo QC, và Báo cáo tóm tắt.

---

## 2026-07-13 19:56

### Bug: Nhãn lịch sử kiểm tra ảnh hiển thị [object Object] ở góc trên bên phải
- **File**: `frontend/index.html` (dòng 1115, 1157-1185)
- **Vấn đề**:
  - Trong `saveHistory()`, thuộc tính `verdict` được gán trực tiếp bằng đối tượng `report.verdict` (được gửi từ Backend dưới dạng dict) thay vì giá trị chuỗi kết quả `report.verdict.result`.
  - Trong `loadHistory()`, badge hiển thị sử dụng trực tiếp `item.verdict` không qua kiểm tra kiểu dữ liệu, gây ra kết quả `[object Object]` khi ép kiểu chuỗi.
- **Sửa**:
  - Cập nhật `saveHistory()` để gán an toàn chuỗi kết quả: `(data.report && data.report.verdict && typeof data.report.verdict === 'object') ? data.report.verdict.result : ((data.report && data.report.verdict) || 'UNKNOWN')`.
  - Cập nhật `loadHistory()` trích xuất an toàn chuỗi `verdictStr` cho cả luồng ảnh và video (tự động phân rã nếu nhận được object cũ trong localStorage).

---

## 2026-07-13 20:13

### Bug: Nhãn kết quả kiểm tra ảnh hiển thị [object Object] ở phần hiển thị kết quả chính
- **File**: `frontend/index.html` (dòng 1141-1148)
- **Vấn đề**: Hàm `displayResults()` cộng chuỗi trực tiếp giá trị `report.verdict` (đang là một đối tượng dict chứa `result`, `reason`, `action_required`) vào HTML khiến nó hiển thị thành `[object Object]`.
- **Sửa**: Phân rã an toàn `report.verdict` trong `displayResults()`. Nếu là object thì lấy thuộc tính `result` làm trạng thái (ĐẠT / CẢNH BÁO / KHÔNG ĐẠT) và `reason` làm mô tả chi tiết, đồng thời đổi icon kết quả động tương ứng.

