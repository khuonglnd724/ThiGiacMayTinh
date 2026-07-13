# Plan: Fix UI - Video Results và History

## Goal
Khắc phục các lỗi giao diện: tiếng Việt mất dấu, thiếu VQA chat box trong video results, history không lưu video, thứ tự nội dung video bị xáo trộn.

---

## 1. Khôi phục tiếng Việt có dấu + VQA Chat Box cho Image Results

### Input
- File `frontend/index.html`
- Toàn bộ text tiếng Việt đang bị mất dấu (VD: "anh duy nhat" thay vì "ảnh duy nhất")
- Hàm `displayResults()`: mất phần VQA chat box (input + nút Hỏi + answer container) sau khi ghi đè file

### Output
- Text tiếng Việt hiển thị đúng dấu
- Image results có VQA chat box để user nhập câu hỏi tự do

### How to do
- Sửa toàn bộ chuỗi text trong file, thay các từ không dấu thành có dấu
- Thêm lại VQA chat form vào cuối `displayResults()`:
  - Input text + nút "Hỏi" (gọi `askVQAQuestion()`)
  - Container hiển thị câu trả lời (`.vqa-answer-box`)
  - CSS cho VQA chat đã có sẵn

---

## 2. Bổ sung VQA Free-form Chat Box cho Video Results

### Input
- `renderVideoResultsOnly()` và `displayVideoResults()` không có VQA chat input
- `displayResults()` đã có VQA chat box (input + nút Hỏi + answer container)

### Output
- Video results cũng hiển thị VQA chat box như image results

### How to do
- Thêm VQA chat form vào cuối `renderVideoResultsOnly()` và `displayVideoResults()`
- Sử dụng `selectedFile` - nếu null thì ẩn hoặc hiển thị thông báo chọn ảnh

---

## 3. Lưu video history vào localStorage

### Input
- `saveVideoHistory()` đã tồn tại nhưng `saveHistory()` chỉ lưu image
- Khi load history, video items hiển thị đúng

### Output
- Video processing results được lưu vào history và hiển thị khi click

### How to do
- Xác nhận `saveVideoHistory()` được gọi trong `displayVideoResults()` (đã có)
- Kiểm tra `loadHistory()` render đúng video items
- Kiểm tra `restoreVideoResult()` hoạt động

---

## 4. Sắp xếp lại thứ tự nội dung Video Results

### Input
- Hiện tại thứ tự hiển thị đang bị xáo trộn giữa: defect cards, frame gallery, report, VQA

### Output
- Thứ tự chuẩn:
  1. **Verdict badge + Summary stats** (đã có)
  2. **Frame Gallery** ("Frame đã quét") - lưới thumbnail tất cả frame
  3. **Defect Detail Cards** - mỗi frame lỗi có: ảnh lớn + enriched predictions + report + VQA
  4. **VQA Chat Box** - form hỏi đáp tự do (nếu có ảnh gốc)

### Phân tích: Cấu trúc hiển thị cho từng frame
**Phương án A (đề xuất) - Frame gallery → Từng frame lỗi chi tiết:**
- "Frame đã quét": Grid thumbnail tất cả frame (cả pass và fail)
- Với mỗi frame lỗi: card riêng với:
  - Ảnh annotated lớn + timestamp
  - Enriched predictions (defect_type, area, severity, position)
  - Inspection report (verdict, recommendations) cho frame đó
  - VQA quick answers cho frame đó
- Tổng hợp: Report tổng thể cho toàn bộ video (số defect, pass rate)

**Phương án B - Tổng hợp tất cả dưới gallery:**
- "Frame đã quét": Grid thumbnail
- "Danh sách lỗi": Tất cả predictions từ tất cả frame gộp lại
- "Khuyến cáo chung": Report tổng thể
- "Hỏi đáp": VQA tổng thể

**Chọn phương án A**: Vì mỗi frame là một ảnh sản phẩm riêng, cần hiển thị chi tiết cho từng frame để QC dễ đánh giá.

### How to do
1. `renderVideoResultsOnly()` sửa thứ tự:
   - Verdict + Stats
   - Frame Gallery (grid thumbnail)
   - Loop each defect frame → card với enriched predictions + report + VQA
   - VQA chat box (free-form)

2. `displayVideoResults()` tương tự

---

## 5. Thứ tự thực hiện

1. Sửa tiếng Việt có dấu (ưu tiên 1)
2. Sắp xếp lại thứ tự video results (ưu tiên 2)
3. Bổ sung VQA chat box cho video (ưu tiên 3)
4. Kiểm tra video history (ưu tiên 4)
5. Cập nhật log

---

## Lưu ý
- File `frontend/index.html` lớn (~1600 dòng), cần thao tác cẩn thận
- Dùng `write_to_file` nếu `replace_in_file` không khớp
- Ghi log vào `log/fix_video_history_log.md` sau mỗi thay đổi