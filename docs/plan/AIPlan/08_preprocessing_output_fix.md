Goal: Sửa output preprocessing để giải quyết NaN loss + CUDA crash khi train YOLO-seg

Nguyên nhân gốc rễ (đã phân tích):
- Good samples được tạo label file rỗng (do mask_to_yolo_segmentation trả về "" khi mask toàn 0) và mask toàn đen
- Label rỗng bị xóa (bằng tay hoặc script cleanup) → ảnh mất label → YOLO coi là background
- Batch chứa quá nhiều background (do good_ratio cao) → không có positive target → task-aligned assigner crash → NaN loss → model params NaN → CUDA crash ở make_anchors
- File mask .png toàn đen cho good samples được lưu nhưng YOLO không dùng → tốn I/O vô ích

Input:
- `AI/preprocess/preprocess.py` (phiên bản hiện tại)
- `AI/preprocess/output/` (dữ liệu đã xử lý từ lần chạy trước, cần xoá sạch)

Output:
- Cập nhật `AI/preprocess/preprocess.py` với logic xử lý good samples đúng
- Xoá sạch output cũ, chạy lại preprocessing để tạo bộ dữ liệu sạch
- Bộ dữ liệu mới: good samples CHỈ có ảnh (ko label, ko mask); defect samples có ảnh + mask + label polygon
- Số lượng good samples được cân bằng (good_ratio ~0.3) để tránh mất cân bằng batch

How to do:
1. Sửa `write_sample()` trong `preprocess.py`:
   - Nếu mask toàn đen (good sample): chỉ copy image, KHÔNG tạo label file, KHÔNG tạo mask file
   - Nếu mask có foreground (defect): tạo image + mask PNG + label polygon như hiện tại

2. Sửa `mask_to_yolo_segmentation()`:
   - Giữ nguyên logic trả về "" nếu mask trống (dùng cho defect check ở process_records)
   - Không ghi file nếu kết quả rỗng (xử lý ở write_sample)

3. Tối ưu `balance_good_samples()`:
   - Chỉ downsample good samples ở train split (đã đúng)
   - Set good_ratio mặc định = 0.3 (thay vì 0.1) để giữ đủ good cho model học "normal"
   - Giữ ratio có thể cấu hình qua CLI --good-ratio

4. Chạy lại preprocessing:
   ```bash
   python AI/preprocess/preprocess.py --good-ratio 0.3 --augment-count 3
   ```
   (Lưu ý: sẽ không còn label rỗng để cleanup, nên ko cần chạy validate_labels.py)

5. Xác nhận output:
   - Thư mục labels/ và masks/ chỉ chứa defect samples (không có good samples)
   - Thư mục images/ chứa cả good + defect
   - Số lượng defect > good trong train split (nhờ good_ratio=0.3)

6. Chạy smoke test để verify training không còn NaN:
   ```bash
   python AI/train/train.py --epochs 5 --batch 4 --smoke-test
   ```

7. Nếu OK, chạy training đầy đủ:
   ```bash
   python AI/train/train.py --model yolo11n-seg.pt --epochs 100 --batch 4 --accumulate 8 --lr0 0.001 --weight-decay 0.01 --optimizer AdamW --device 0 --no-amp
   ```

Lưu ý:
- Giữ nguyên cấu trúc thư mục images/train/{class}/ cho good samples (chỉ ko tạo label + mask)
- YOLO native support ảnh không có label → tự động coi là background image
- good_ratio=0.3 giữ ~30% good so với số defect, đủ để model học "thế nào là normal" mà ko overwhelm
- Nếu vẫn còn NaN, check thêm lr0 (giảm xuống 5e-4) và warmup epochs

