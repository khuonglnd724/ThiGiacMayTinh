# Frontend — Ghi chú và hướng dẫn

Tổng quan:

- Frontend là phần giao diện tĩnh của dự án, nằm trong thư mục `frontend/`.
- Nội dung chính: trang chính `index.html`, mã JavaScript trong `frontend/js/`, và CSS trong `frontend/css/`.

Cấu trúc thư mục quan trọng:

- `frontend/index.html`: entry point của ứng dụng.
- `frontend/assets/`: ảnh, font, và tài nguyên tĩnh khác.
- `frontend/css/`: file `style.css`, `responsive.css`.
- `frontend/js/`: tập hợp các script: `app.js`, `api.js`, `ui.js`, `utils.js`.

Cách chạy локal:

1. Dùng một web server tĩnh để phục vụ thư mục `frontend/` (không mở trực tiếp file bằng `file://` nếu có gọi API). Ví dụ nhanh bằng Python:

```
python -m http.server 8000 --directory frontend
```

2. Mở trình duyệt tại `http://localhost:8000`.

API backend:

- Frontend gọi API do backend cung cấp (xem cấu hình trong `backend/config.py`). Đảm bảo backend đang chạy trước khi test tính năng liên quan tới dữ liệu.

Xây dựng & triển khai:

- Hiện tại frontend là tĩnh — không có pipeline bundler mặc định. Nếu muốn tối ưu hoá, thêm `package.json` + công cụ như Webpack, Vite hoặc Parcel.
- Để triển khai, copy toàn bộ nội dung `frontend/` lên server tĩnh hoặc CDN (ví dụ Netlify, GitHub Pages).

Gợi ý phát triển:

- Khi thay đổi API, cập nhật `frontend/js/api.js` tương ứng.
- Tổ chức mã UI trong `frontend/js/ui.js` để giữ phần xử lý DOM tách biệt khỏi logic mạng.
- Đặt ảnh và tệp lớn vào `frontend/assets/` để dễ quản lý.

Vấn đề thường gặp:

- Lỗi CORS khi backend chưa cấu hình cho phép origin từ frontend — kiểm tra header CORS trên backend.
- Tải file tĩnh không đúng đường dẫn — kiểm tra đường dẫn tương đối trong `index.html`.

Muốn mình mở rộng thêm phần hướng dẫn setup với bundler hoặc thêm ví dụ cụ thể cho các endpoint API không? 
