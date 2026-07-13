# Plan: Fix History & VQA Issues

## Goal
Khắc phục 3 vấn đề:
1. **Video history không lưu** khi xử lý video
2. **History image hiển thị [object Object]** thay vì số liệu
3. **VQA free-form chat trả lời 1 câu duy nhất** cho mọi câu hỏi

---

## 1. Video history không lưu

### Input
- File `frontend/index.html`
- Hàm `processSelectedVideo()` gọi `renderVideoResultsOnly()` — hàm này không gọi `saveVideoHistory()`
- Chỉ `displayVideoResults()` mới gọi `saveVideoHistory()`

### Output
- Video processing results được lưu vào localStorage history

### How to do
- Thêm `saveVideoHistory(result)` vào cuối `renderVideoResultsOnly()`

---

## 2. History image hiển thị [object Object]

### Input
- File `frontend/index.html`
- `normalizeCount()` gặp object (ví dụ severity object) không parse được, trả về chính object đó
- Khi concat vào HTML → `[object Object]`

### Output
- Hiển thị số đúng (0, 1, 2...) thay vì `[object Object]`

### How to do
- Sửa `normalizeCount()`: thêm check `typeof value === 'object' && value !== null` → return fallback
- Sửa `displayResults()`: `const total_defects = (typeof data.total_defects === 'number') ? data.total_defects : 0;`

---

## 3. VQA free-form chat trả lời 1 câu duy nhất

### Input
- Backend `backend/services/vqa_service.py` — 3 modes theo thứ tự ưu tiên:
  1. **Context-aware** (dùng inspection report) — ✅ trả lời chính xác nhất
  2. **Transformers** (dandelin/vilt-b32-finetuned-vqa) — ⚠️ cần tải model ~1.5GB
  3. **Keyword fallback** — ❌ chỉ có 4 pattern, fallback luôn trả 1 câu

### Nguyên nhân chính
- Frontend `apiClient.askVQA(selectedFile, question)` gọi `/vqa` endpoint
- Backend `/vqa` endpoint gọi `vqa_service.answer_question(img, question)` **KHÔNG có `inspection_context`**
- → Mode 1 (context-aware) bị bỏ qua
- → Mode 2 (Transformers) có thể fail nếu chưa tải model
- → Mode 3 (keyword fallback) chỉ có 4 pattern, câu nào không khớp → trả về câu mặc định

### Output
- VQA trả lời khác nhau cho các câu hỏi khác nhau, tận dụng context-aware mode

### Giải pháp tối ưu: Kết hợp truyền Context từ Frontend & Cải tiến Keyword Fallback
Hệ thống không lưu context tĩnh của ảnh đơn lẻ trong database (do DB chỉ lưu log video băng tải). Do đó, giải pháp tốt nhất là:

1. **Frontend (`frontend/index.html`)**:
   - Định nghĩa một biến toàn cục `window.lastInspectionData = null;` để lưu kết quả trả về từ API `/inspect` (gồm `predictions` và `report`).
   - Khi gọi `apiClient.askVQA(selectedFile, question, window.lastInspectionData)`, truyền thêm tham số `lastInspectionData`.

2. **Backend Endpoint (`backend/main.py`)**:
   - Sửa endpoint `/vqa` nhận thêm trường `context: Optional[str] = Form(None)`.
   - Nếu có `context`, parse JSON chuỗi này thành dictionary và truyền vào `vqa_service.answer_question(img, question, inspection_context=context)`.

3. **Backend Service (`backend/services/vqa_service.py`)**:
   - Sử dụng `inspection_context` cho Mode 1 (Context-aware).
   - Đồng thời, cải tiến thêm Mode 3 (`_keyword_fallback`) để khi không có context vẫn trả lời đa dạng hơn (phòng ngừa trường hợp người dùng hỏi VQA khi chưa chạy Inspect).

### Chi tiết cách làm

**Phần Backend `/vqa` (`backend/main.py`):**
- Import `Optional` và `json`.
- Định nghĩa lại endpoint `/vqa`:
  ```python
  @app.post("/vqa")
  async def vqa(file: UploadFile = File(...), question: str = Form(...), context: Optional[str] = Form(None)):
      ...
      inspection_context = None
      if context:
          try:
              inspection_context = json.loads(context)
          except Exception:
              pass
      result_answer = vqa_service.answer_question(img, question, inspection_context=inspection_context)
  ```

**Phần Frontend (`frontend/index.html`):**
- Khi gọi `apiClient.inspectImage(...)` thành công, lưu: `window.lastInspectionData = result;`.
- Trong hàm `askVQAQuestion()`, đổi thành:
  ```javascript
  apiClient.askVQA(selectedFile, question, window.lastInspectionData)
  ```

**Phần VQA Fallback (`backend/services/vqa_service.py`):**
- Cải thiện `_keyword_fallback()` với nhiều pattern phong phú hơn (hỗ trợ cả tiếng Anh lẫn tiếng Việt).

### Lưu ý
- Context-aware mode cần `inspection_context` với `enriched_predictions` và `report`
- Transformers model (dandelin/vilt-b32-finetuned-vqa) cần ~1.5GB RAM và thời gian tải
- Keyword fallback là giải pháp nhanh nhất, không cần tải model

---

## 4. Thứ tự thực hiện

1. Sửa `normalizeCount()` — fix [object Object]
2. Thêm `saveVideoHistory()` vào `renderVideoResultsOnly()` — lưu video history
3. Cải thiện `_keyword_fallback()` trong vqa_service.py — VQA trả lời đa dạng
4. (Optional) Frontend lưu `lastInspectionData` và gửi context khi gọi VQA
5. Cập nhật log

---

## Lưu ý
- Tuân thủ rule.md: ghi log vào `log/` sau mỗi thay đổi
- File plan không quá 200 dòng