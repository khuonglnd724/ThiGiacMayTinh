Goal: Tải và chuẩn hoá bộ dữ liệu MVTec AD vào dự án

Input:
- Yêu cầu: bộ dữ liệu MVTec AD (kaggle ipythonx/mvtec-ad) hoặc nguồn thay thế
- Đích: thư mục `AI/dataset`

Output:
- Dữ liệu thô cho mỗi class nằm trong `AI/dataset/mvtec-ad/<class>/`
- File kiểm tra (manifest) liệt kê đường dẫn ảnh và mặt nạ cho từng split

How to do:
1. Tải dataset từ Kaggle hoặc nguồn thay thế. Lưu vào `AI/dataset/mvtec-ad/`.
2. Kiểm tra cấu trúc: các thư mục per-class, trong mỗi thư mục có `good/` và `defect/` hoặc tương tự.
3. Viết script `scripts/download_mvtec.py` (tuỳ chọn) dùng Kaggle API hoặc sao chép thủ công.
4. Tạo danh sách ảnh và mặt nạ, chuẩn bị manifest CSV/JSON để phục vụ bước chia split.
5. Chia dữ liệu Train/Val/Test theo tỉ lệ 70/20/10, đảm bảo seed cố định để tái lập.

Lưu ý:
- Nếu không có mặt nạ segmentation sẵn, cần tạo mask bằng công cụ thủ công hoặc bán tự động.
- Tuân thủ bản quyền và điều khoản Kaggle khi tải dữ liệu.
