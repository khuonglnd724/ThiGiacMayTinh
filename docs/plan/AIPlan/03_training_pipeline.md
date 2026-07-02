Goal: Xây dựng và chạy pipeline huấn luyện mô hình phân vùng + phát hiện lỗi (YOLO-seg)

Input:
- Dữ liệu đã chuẩn hoá và manifest (theo YOLO format)
- Môi trường Python với PyTorch, thư viện YOLO-seg hoặc Ultralytics
- Thông tin phần cứng (đã ghi trong overview)

Output:
- Tập checkpoints, file `best.pt` (trọng số tốt nhất), logs (tensorboard/W&B)

How to do:
1. Chọn mô hình nhẹ: yolov8n-seg hoặc YOLO11-seg variant nhỏ; tải pretrained weights.
2. Viết `train.py` có options: --img, --batch, --epochs, --device, --accumulate, --amp, --workers.
3. Đặt mặc định cho môi trường VRAM nhỏ: img=416, batch=2, accumulate=8, amp=True.
4. Sử dụng AdamW, lr bắt đầu 1e-4, weight_decay=1e-2, scheduler CosineWarmup hoặc ReduceLROnPlateau.
5. Ghi checkpoint khi validation metric cải thiện; xác định metric ưu tiên (recommend: mAP + hạn chế FN).
6. Chạy smoke test 1 epoch trên subset để xác thực forward/backward và checkpointing.

Lưu ý:
- Dùng gradient accumulation để đạt hiệu quả batch lớn hơn trên VRAM nhỏ.
- Kích thước ảnh lớn (640) có thể OOM trên GTX1650; giảm xuống 416/320 nếu cần.
