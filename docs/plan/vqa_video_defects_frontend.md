# VQA cho từng Defect trong Video (Frontend-only)

## Goal
Cho phép người dùng đặt câu hỏi (VQA) về **từng defect cụ thể** trong mỗi frame của kết quả video, thay vì chỉ có 1 ô chat chung cho toàn bộ video.

## Input
- Kết quả từ backend `/process_video`: mỗi log trong `logs[]` chứa:
  - `saved_image_url`: URL ảnh annotate của frame
  - `predictions[]`: danh sách predictions đã enrich (defect_type, area, position, severity, ...)
  - `report`: inspection report của frame
- Câu hỏi người dùng nhập (ví dụ: "Lỗi này nặng không?", "Vị trí ở đâu?")

## Output
- Mỗi defect card trong kết quả video có 1 VQA riêng:
  - Ô input text + nút "Hỏi"
  - Hiển thị câu trả lời từ backend `/vqa`
- Không thay đổi backend, không cần deploy lại backend

## How to do

### 1. Cơ chế lấy ảnh gốc của defect
- Backend `/vqa` cần file ảnh (multipart), không nhận URL
- Frontend sẽ:
  - Fetch ảnh từ `saved_image_url` bằng `fetch()` với `response.blob()`
  - Tạo File object từ Blob
  - Append vào FormData cùng với `question` và `context` (JSON string chứa prediction của defect đó)
  - Gửi lên endpoint `/vqa`

→ Chỉ sửa frontend, không cần thêm backend endpoint

### 2. Thêm VQA vào mỗi defect card trong kết quả video
- Khi render kết quả video (`renderVideoResultsOnly` / `displayVideoResults`):
  - Với mỗi frame có lỗi và mỗi prediction trong frame đó:
    - Thêm 1 VQA section riêng trong defect card
    - Gồm: ô input + nút "Hỏi" + container hiển thị câu trả lời
- Khi người dùng nhấn "Hỏi":
  1. Fetch ảnh frame từ `saved_image_url` → Blob
  2. Tạo context JSON chứa prediction của defect đó (defect_type, area, position, severity, confidence)
  3. Gọi `apiClient.askVQA(file, question, context)`
  4. Hiển thị câu trả lời trong container của defect đó

### 3. Các file cần sửa

**File: `frontend/index.html`**
- Trong phần `renderVideoResultsOnly()` và `displayVideoResults()`:
  - Sửa vòng lặp render predictions để thêm VQA per defect
  - Thêm CSS cho VQA per defect (có thể thêm inline style hoặc thêm vào <style>)

**File: `frontend/js/api.js`**
- Thêm method mới: `async askVQAFromUrl(imageUrl, question, context)` 
  - Fetch ảnh từ URL → Blob → gửi lên `/vqa`
  - Giữ nguyên method `askVQA()` cũ cho ảnh upload trực tiếp

### 4. Chi tiết luồng xử lý

```
[User nhấn "Hỏi" trên defect card]
    │
    ├── Fetch ảnh từ saved_image_url → response.blob()
    │
    ├── Tạo File từ Blob (filename = frame_{idx}_defect_{d}.jpg)
    │
    ├── Build context = {
    │     "enriched_predictions": [prediction của defect đó],
    │     "report": frame.report (nếu có)
    │   }
    │
    ├── Gọi apiClient.askVQA(file, question, JSON.stringify(context))
    │
    └── Hiển thị answer trong container của defect đó
```

## Lưu ý
- Method `askVQA()` trong `api.js` đã hỗ trợ gửi context JSON qua FormData
- Cần xử lý loading state riêng cho mỗi defect (không block toàn trang)
- Cần xử lý lỗi riêng cho mỗi defect (không ảnh hưởng các defect khác)
- Chỉ fetch ảnh khi người dùng click "Hỏi", không prefetch
- CSS cần responsive cho VQA input trong defect card nhỏ