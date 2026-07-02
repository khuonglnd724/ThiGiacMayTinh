# 🚀 Quick Start Guide - Frontend

## ⚡ 2 Phút Setup

### 1. Đảm bảo Backend Chạy

```bash
cd backend
python main.py
```

✅ Backend sẽ chạy trên `http://localhost:8000`

### 2. Chạy Frontend

**Option A: Với Python**
```bash
cd frontend
python -m http.server 3000 --directory .
```

**Option B: Với Node.js**
```bash
cd frontend
npx http-server . -p 3000
```

**Option C: VS Code Live Server**
- Right-click `index.html` → "Open with Live Server"

✅ Frontend sẽ chạy trên `http://localhost:3000`

---

## 📱 Truy Cập Giao Diện

**URL**: http://localhost:3000

### Các Trang Chính

| Trang | URL | Phím Tắt |
|------|-----|----------|
| Dashboard | /#dashboard | Ctrl+D |
| Upload | /#upload | Ctrl+U |
| Results | /#results | - |
| History | /#history | Ctrl+H |
| Settings | /#settings | - |

---

## 📋 Hướng Dẫn Sử Dụng

### 1. Upload Ảnh
1. Vào trang "Upload & Inspect"
2. **Kéo thả** ảnh vào vùng upload
   - Hoặc **nhấp** để chọn file
3. Điều chỉnh "Confidence Threshold" (nếu cần)
4. Nhấp "🚀 Start Inspection"

### 2. Xem Kết Quả
- **Ảnh annotate** (bounding box + mask)
- **Defects detected** (danh sách lỗi)
- **Inspection Report** (tóm tắt, khuyến cáo)
- **VQA Answers** (câu trả lời tự động)

### 3. Xem Lịch Sử
1. Vào trang "History"
2. Lọc theo Verdict (All / PASS / FLAG / REJECT)
3. Nhấp "View" để xem chi tiết
4. Nhấp "Delete" để xoá bản ghi

### 4. Cài Đặt
1. Vào trang "Settings"
2. Điều chỉnh:
   - Confidence Threshold mặc định
   - Frame Skip Rate
   - Dark Mode
3. Nhấp "💾 Save Settings"

---

## ⌨️ Keyboard Shortcuts

```
Ctrl + U → Upload page
Ctrl + H → History page
Ctrl + D → Dashboard
Ctrl + T → Toggle Dark Mode
```

---

## 🎨 Giao Diện

### Theme
- 🌙 Mặc định: **Light Mode** (sáng)
- Nhấp icon 🌙 trên navbar để đổi Dark Mode
- Tự động lưu lại

### Dữ Liệu
- Tất cả settings lưu vào **LocalStorage**
- Không cần đăng nhập

---

## 🔧 Troubleshooting

### ❌ Lỗi: Cannot connect to backend

**Giải pháp:**
1. Kiểm tra backend chạy: `python main.py` (Terminal 1)
2. Kiểm tra port: http://localhost:8000
3. Kiểm tra CORS enabled trong backend

### ❌ Lỗi: CORS Policy error

**Giải pháp:**
Thêm vào `backend/main.py`:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### ❌ Ảnh không hiển thị

**Giải pháp:**
- Kiểm tra file format (JPEG, PNG, BMP, TIFF)
- Kiểm tra kích thước file < 50MB
- Kiểm tra browser console (F12) xem lỗi

### ❌ Settings không lưu

**Giải pháp:**
- Kiểm tra browser cho phép LocalStorage
- Không dùng Incognito mode
- Xóa cache & refresh page

---

## 📊 Dashboard

Hiển thị:
- **Total Inspections**: Số lần inspect
- **Passed**: ✅ Số sản phẩm đạt tiêu chuẩn
- **Flagged**: ⚠️ Số cần kiểm tra lại
- **Rejected**: ❌ Số bị từ chối

---

## 📤 Upload & Inspect

### Input
- Ảnh: JPEG, PNG, BMP, TIFF
- Hoặc video: MP4, AVI, MOV

### Output
```json
{
  "predictions": [
    {
      "defect_type": "scratch",
      "confidence": 0.95,
      "area": 12.5,
      "position": "top_left",
      "severity": "High"
    }
  ],
  "annotated_image_path": "/results/image_123.png",
  "report": {
    "verdict": "REJECT",
    "summary": "...",
    "recommendations": [...]
  },
  "vqa_answers": {
    "Có lỗi không?": "Có, phát hiện 1 lỗi",
    "Lỗi ở đâu?": "Ở phía trên bên trái",
    ...
  }
}
```

---

## ✅ Verdict Types

| Verdict | Ý Nghĩa | Màu |
|---------|---------|-----|
| **PASS** | ✅ Đạt tiêu chuẩn | 🟢 Green |
| **FLAG** | ⚠️ Cần kiểm tra lại | 🟡 Amber |
| **REJECT** | ❌ Bị từ chối | 🔴 Red |

---

## 📋 History

### Xem Chi Tiết
1. Nhấp "View" trên bảng History
2. Modal hiển thị JSON đầy đủ
3. Nhấp "Close" để đóng

### Lọc & Tìm Kiếm
- Filter theo Verdict: All / PASS / FLAG / REJECT
- Pagination: 10 items/page
- Nhấp nút "Previous/Next" để chuyển trang

---

## ⚙️ Settings

### Confidence Threshold
- **Giá trị**: 0.0 - 1.0 (default 0.25)
- **Ý nghĩa**: Độ tin cậy tối thiểu để phát hiện lỗi
- **↑ Cao hơn**: Ít phát hiện lỗi hơn, độ chính xác cao
- **↓ Thấp hơn**: Phát hiện nhiều lỗi hơn, có thể sai

### Frame Skip Rate (cho Video)
- **Giá trị**: 1 - 30 (default 5)
- **Ý nghĩa**: Xử lý mỗi N frame
- **Ví dụ**: skip=5 → xử lý frame 0, 5, 10, 15...

### Dark Mode
- Toggle để bật/tắt
- Tự động lưu lại

---

## 🔍 Browser DevTools

### Xem Logs
```
Nhấn F12 → Console tab
Xem messages, warnings, errors
```

### Kiểm Tra Network
```
F12 → Network tab
Xem các API requests/responses
```

### Kiểm Tra Storage
```
F12 → Application tab
Xem LocalStorage values
```

---

## 🆘 Cần Giúp?

### Xem Documentations
1. `frontend/README.md` - Hướng dẫn chi tiết
2. `docs/plan/frontend_plan.md` - Thiết kế
3. `docs/plan/frontend_integration.md` - Tích hợp
4. `docs/plan/system_overview.md` - Tổng quan hệ thống

### Kiểm Tra Backend
- Xem `docs/plan/backend_api.md`
- Xem `backend/main.py`

### View Logs
- `log/frontend_development.md` - Nhật ký phát triển
- `log/FRONTEND_SUMMARY.md` - Tóm tắt

---

## 🎯 Workflow Ví Dụ

### Quy trình Kiểm Tra Sản Phẩm

1. **Mở Dashboard**
   - Xem tổng thống kê
   - Xem recent inspections

2. **Upload Ảnh**
   - Trang "Upload & Inspect"
   - Kéo thả ảnh
   - Chỉnh "Confidence" nếu cần
   - Nhấp "Start Inspection"

3. **Phân Tích Kết Quả**
   - Xem ảnh annotate
   - Xem danh sách lỗi
   - Đọc report
   - Xem VQA answers

4. **Lưu & Tiếp Tục**
   - Kết quả tự động lưu vào database
   - Vào "History" để xem lại
   - Tiếp tục upload ảnh khác

---

## 📈 Performance Tips

1. **Giảm kích thước ảnh**
   - Nén ảnh trước khi upload
   - Max 5MB là tốt

2. **Điều chỉnh Confidence**
   - Confidence cao → xử lý nhanh hơn
   - Confidence thấp → chính xác hơn

3. **Clear History Định Kỳ**
   - Vào Settings → "Clear All Settings"
   - Hoặc delete individual records

4. **Refresh Page**
   - Nếu chậm, refresh page (F5)

---

## 🎁 Bonus

### Keyboard Navigation
- Tab: Di chuyển giữa elements
- Enter: Activate button
- Space: Toggle checkbox
- Arrow keys: Navigate menu

### Export Dữ Liệu
- History có thể export JSON (từ browser DevTools)
- Inspection details có thể copy từ modal

### Screen Recording
- Để record inspection process
- Sử dụng OBS hoặc Screen Recorder

---

## ✨ Tính Năng

✅ Modern responsive UI  
✅ Dark/Light mode  
✅ Real-time processing  
✅ History management  
✅ Settings persistence  
✅ Keyboard shortcuts  
✅ Error handling  
✅ Loading indicators  
✅ Mobile friendly  
✅ Accessible design  

---

## 📞 Contact

- Xem file `docs/` cho thêm thông tin
- Xem `log/` cho development history
- Kiểm tra `frontend/README.md` cho details

---

**Status**: ✅ Ready to Use
**Version**: 1.0.0
**Last Updated**: 2024

🎉 **Bắt đầu ngay**: http://localhost:3000
