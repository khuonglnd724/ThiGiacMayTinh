# Kế hoạch Triển khai Backend API và Quy trình Xử lý Video (MVTec AD & YOLO-seg)

Goal: Xây dựng FastAPI backend có nhiệm vụ nhận video đầu vào, trích xuất khung hình chứa sản phẩm để kiểm tra chất lượng bằng mô hình YOLO, lưu kết quả nhận diện và phân vùng lỗi vào cơ sở dữ liệu SQLite, và trả kết quả JSON phục vụ Frontend.

## Input
- File video tải lên từ giao diện web (định dạng .mp4, .avi, v.v.).
- Mô hình YOLO-seg đã huấn luyện (best.pt hoặc pretrained).
- Các cấu hình: Ngưỡng tự tin (confidence threshold), tỷ lệ nhảy khung hình (frame skip) để tối ưu hiệu năng.

## Output
- Database SQLite chứa thông tin lịch sử kiểm tra chất lượng sản phẩm (bảng `inspection_logs`).
- Các khung hình phát hiện lỗi được vẽ bounding box và mask (được lưu trong thư mục `static/results`).
- API trả về JSON chứa thông tin tóm tắt kết quả (tổng số khung hình xử lý, số lỗi phát hiện, đường dẫn ảnh kết quả).

## How to do

1. **Khởi tạo FastAPI Backend & Cơ sở dữ liệu:**
   - Tạo cấu trúc thư mục `backend/` chứa `main.py`, `database.py`, `models.py` và `services/`.
   - Sử dụng SQLAlchemy / SQLite để khởi tạo bảng `inspection_logs` gồm các trường:
     - `id`: Khóa chính.
     - `video_name`: Tên video đầu vào.
     - `frame_index`: Chỉ số khung hình trong video.
     - `timestamp`: Thời gian xuất hiện lỗi (giây).
     - `has_defect`: Có lỗi hay không (Boolean).
     - `predictions`: Chuỗi JSON lưu tọa độ box và polygon vết lỗi.
     - `saved_image_path`: Đường dẫn lưu khung hình lỗi thực tế để Frontend hiển thị.
     - `created_at`: Thời gian kiểm tra.

2. **Xây dựng API `POST /process_video`:**
   - Sử dụng `UploadFile` của FastAPI để nhận file video.
   - Lưu video tạm thời vào thư mục `backend/uploads/`.

3. **Pipeline xử lý trích xuất khung hình và suy luận:**
   - Dùng OpenCV (`cv2.VideoCapture`) để đọc video.
   - Lập trình vòng lặp đọc khung hình (cấu hình skip rate, ví dụ chỉ lấy 5-10 frames/giây để tiết kiệm CPU/GPU).
   - **Xác định khung hình có sản phẩm:** Khung hình được đưa qua mô hình YOLO. Nếu phát hiện đối tượng hoặc độ biến đổi pixel trong vùng quan tâm (ROI) thay đổi, khung hình đó sẽ được đưa vào diện kiểm tra.
   - Chạy mô hình YOLO11-seg suy luận trên khung hình:
     - Nếu phát hiện lỗi (defect) với độ tin cậy lớn hơn ngưỡng (ví dụ `conf > 0.25`):
       - Vẽ bounding box và vẽ đè mặt nạ đa giác (segmentation mask) lên ảnh.
       - Lưu ảnh kết quả vào thư mục `backend/static/results/`.
       - Lưu bản ghi kết quả nhận diện (JSON) kèm đường dẫn ảnh vào cơ sở dữ liệu SQLite.
     - Nếu không có lỗi, có thể chọn lưu nhật ký (has_defect = False) mà không cần lưu lại ảnh để tiết kiệm dung lượng ổ đĩa.

4. **Kết nối Frontend (CORS):**
   - Kích hoạt CORS middleware trong FastAPI để cho phép Frontend gửi file video và nhận JSON kết quả.

## Lưu ý
- Xử lý video thời gian thực đòi hỏi tài nguyên lớn. Cần tối ưu bằng cách tăng giá trị frame skip (chỉ xử lý mỗi k khung hình) thay vì xử lý từng khung hình liên tục.
- Trọng số mô hình `best.pt` cần được load một lần duy nhất khi khởi chạy server (dùng cơ chế Lifespan/Startup event của FastAPI) để tránh tải lại mô hình trong mỗi request gây chậm hệ thống.
- Cần dọn dẹp các video tạm thời sau khi xử lý xong để tránh tràn bộ nhớ máy chủ.
