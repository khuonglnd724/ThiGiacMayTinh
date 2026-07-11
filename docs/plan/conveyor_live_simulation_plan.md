# Goal
- Thêm chế độ xử lý video thực tế và giả lập luồng live trên băng chuyền sản xuất để người dùng có thể xem các khung hình được xử lý như một luồng dữ liệu thời gian thực.
- Hỗ trợ tải lên video ghép từ các ảnh sản phẩm, xử lý theo từng frame với YOLO, phát hiện frame lỗi và hiển thị kết quả ngay trên giao diện chính.
- Hiển thị video chạy ở panel bên trái (conveyor live) và kết quả chi tiết trên màn hình chính bao gồm ảnh frame lỗi và thông tin thời gian.
- **Scene Change Detection**: Chỉ xử lý YOLO khi frame thay đổi nội dung, tránh phát hiện trùng lỗi trên cùng một ảnh xuất hiện nhiều frame.

# Input
- Người dùng mở giao diện web và bấm nút Bắt đầu trong panel Conveyor Live.
- Người dùng chọn video (ghép ảnh sản phẩm) để kiểm tra lỗi, hoặc chạy chế độ giả lập.
- Hệ thống có sẵn backend FastAPI, frontend tĩnh và mô hình YOLO đã cấu hình.
- **Tham số `scene_threshold`** (mặc định 30.0): Ngưỡng phát hiện chuyển cảnh, thấp hơn = nhạy hơn.

# Output
- Panel bên trái hiển thị luồng video/giả lập đang chạy, trạng thái stream và nhật ký từng frame.
- Màn hình chính hiển thị video đang chạy, kết quả kiểm tra chi tiết với ảnh frame lỗi và thông tin thời gian lỗi.
- History hiển thị số lượng đạt bên cạnh số lượng lỗi để người dùng đọc nhanh kết quả video và ảnh.
- Backend trả về dữ liệu frame (base64 images) cho giả lập hoặc kết quả video inspection qua endpoint.
- **Response mới**: `unique_images_detected` (số ảnh duy nhất), `is_duplicate` flag cho frame trùng.

# How to do
1. **Backend - Hàm `detect_scene_change()`**: So sánh histogram giữa 2 frame liên tiếp (Chi-square distance), trả về True khi có chuyển cảnh.
2. **Backend - Endpoint /conveyor/simulate**: Sinh dữ liệu frame giả lập với ảnh base64 (SVG) để frontend hiển thị như video stream.
3. **Backend - Endpoint /process_video** (cải tiến với Scene Change Detection):
   - Nhận video upload, duyệt từng frame
   - **Scene Change Detection**: So sánh frame hiện tại với frame trước đó (histogram), nếu khác biệt > threshold → ảnh mới
   - **Chỉ chạy YOLO segmentation khi phát hiện ảnh mới** (scene change)
   - Các frame trùng (cùng 1 ảnh) được ghi log với `"is_duplicate": True` và kế thừa kết quả từ ảnh gốc
   - Phát hiện defect sử dụng hàm is_defect_frame (defect keywords + confidence threshold)
   - Lưu annotated frames (có bounding box + mask) vào static/results (chỉ cho ảnh duy nhất)
   - Trả về summary + logs với `unique_images_detected`, `saved_image_url` cho từng defect frame
4. **Frontend - Cập nhật API Client** (`frontend/js/api.js`):
   - Thay tham số `skipRate` (frame_skip) bằng `sceneThreshold` (scene_threshold)
   - Gọi endpoint với FormData chứa `scene_threshold`
5. **Frontend - Panel Conveyor Live (bên trái)**:
   - Thêm nút chọn video, nút bắt đầu/dừng
   - Hiển thị video/giả lập chạy như stream với interval 500ms
   - Hiển thị log từng frame với verdict và số defect
   - Hiển thị preview frame lỗi gần nhất (có timestamp + số phát hiện)
6. **Frontend - Màn hình chính**:
   - Hiển thị video đang chạy (nếu có video thật) hoặc kết quả giả lập
   - Hiển thị danh sách defect frames với ảnh, thời gian (timestamp), số phát hiện
7. **Kết nối API**: Frontend gọi /conveyor/simulate (giả lập) hoặc /process_video (video thật) và render kết quả.

# Lưu ý
- Video thật cần chứa các ảnh sản phẩm rõ ràng để YOLO có thể phát hiện defect.
- **Scene Change Detection** dùng histogram Chi-square: frame giống nhau → diff ~0, frame khác → diff > 30 (ngưỡng mặc định).
- Frame giả lập sử dụng SVG base64 để không cần lưu file tạm.
- Xử lý video giới hạn max_frames (mặc định 40) để tránh timeout.
- Ảnh defect được lưu trong static/results và hiển thị trực tiếp trên frontend.
- Panel bên trái chạy như live stream, màn hình chính hiển thị kết quả chi tiết.
- Tham số `scene_threshold` có thể điều chỉnh: thấp hơn nếu video ảnh đơn sắc, cao hơn nếu video có nhiều chuyển động nhẹ.
- Frontend normalize số liệu trước khi render để tránh hiển thị `[object Object]` ở các ô thống kê và nhãn defect.
