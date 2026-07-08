# Plan: Test & Evaluate Model

## Goal
Xây dựng script `evaluate.py` để test và đánh giá toàn diện model segmentation đã huấn luyện (best.pt) trên tập test của MVTec AD. Script này cho phép:
- Chạy inference trên toàn bộ test set
- Tính toán các metrics đánh giá (Precision, Recall, mAP, IoU, Dice, F1)
- So sánh kết quả per-class và per-category (bottle, cable, capsule, ...)
- Tạo báo cáo chi tiết dạng JSON/CSV kèm visualization
- Hỗ trợ chạy trên single image để debug nhanh

## Input
- **Model checkpoint**: `runs/segment/AI/train/runs/ai-segmentation/segmentation/weights/best.pt` (có thể tuỳ chỉnh path)
- **Data config**: `AI/train/data.yaml` (chứa path dataset, class names)
- **Test dataset**: Thư mục `AI/preprocess/output/images/test/` và `AI/preprocess/output/labels/test/` (cấu trúc per-class)
- **Tham số CLI**:
  - `--model`: path đến best.pt (mặc định: path trên)
  - `--data-yaml`: path đến data.yaml (mặc định: AI/train/data.yaml)
  - `--imgsz`: kích thước ảnh đầu vào (mặc định: 640)
  - `--batch`: batch size (mặc định: 1)
  - `--device`: thiết bị (auto/0/cpu)
  - `--conf`: confidence threshold (mặc định: 0.25)
  - `--iou`: NMS IoU threshold (mặc định: 0.45)
  - `--output-dir`: thư mục lưu kết quả (mặc định: AI/evaluate/output)
  - `--single-image`: path đến 1 ảnh để test nhanh (optional)
  - `--save-images`: flag để lưu ảnh kèm prediction overlay

## Output
- **Báo cáo metrics tổng quan** (JSON): lưu tại `{output_dir}/evaluation_report.json`
  - mAP@0.5, mAP@0.5:0.95 (box & mask)
  - Precision, Recall, F1-score (box & mask)
  - Mean IoU, Mean Dice cho segmentation masks
  - Số lượng FP, FN, TP per-class
- **Báo cáo per-class** (CSV): `{output_dir}/per_class_metrics.csv`
- **Confusion Matrix** (image): `{output_dir}/confusion_matrix.png`
- **Ảnh overlay** (nếu `--save-images`): `{output_dir}/predictions/{class_name}/` chứa ảnh gốc + prediction overlay
- **Bảng tổng hợp so sánh các lần train** (nếu có nhiều best.pt từ các run khác nhau)

## How to do

### 1. Tạo cấu trúc thư mục
- Tạo `AI/evaluate/` chứa `evaluate.py` và thư mục `output/` để lưu kết quả.

### 2. Xây dựng evaluate.py

#### 2.1. Load model & data
- Dùng `ultralytics.YOLO` load model từ best.pt
- Parse data.yaml để lấy class names và path test set
- Load test images từ `{dataset_root}/images/test/{class_name}/*.jpg`
- Load ground-truth labels từ `{dataset_root}/labels/test/{class_name}/*.txt`

#### 2.2. Chạy inference
- Chạy `model.predict()` trên test set với các tham số: imgsz, batch, device, conf, iou
- Kết quả trả về gồm: boxes (detection) và masks (segmentation)

#### 2.3. Tính metrics

**Detection metrics (Box)**:
- Sử dụng `ultralytics.utils.metrics` hoặc tự tính:
  - Với mỗi ảnh, so sánh predicted boxes vs ground-truth boxes
  - Tính TP/FP/FN dựa trên IoU threshold (mặc định 0.5)
  - Tính Precision = TP / (TP + FP), Recall = TP / (TP + FN)
  - Tính mAP@0.5 và mAP@0.5:0.95

**Segmentation metrics (Mask)**:
- Với mỗi predicted mask, so sánh pixel-wise với ground-truth mask
- Tính IoU = intersection / union
- Tính Dice = 2 * intersection / (sum(pred) + sum(gt))
- Tính mean IoU và mean Dice trên tất cả samples

#### 2.4. Tạo báo cáo
- Ghi `evaluation_report.json` với đầy đủ metrics
- Ghi `per_class_metrics.csv` với metrics cho từng class
- Vẽ confusion matrix bằng matplotlib/seaborn
- Nếu `--save-images`: vẽ prediction overlay (bounding box + mask) lên ảnh gốc và lưu

#### 2.5. So sánh nhiều runs (optional)
- Nếu phát hiện nhiều thư mục run trong `runs/segment/AI/train/runs/ai-segmentation/`, cho phép so sánh metrics giữa các runs
- Tạo bảng so sánh dạng CSV/JSON

### 3. Xử lý edge cases
- Ảnh không có defect (good sample): ground-truth mask rỗng → predicted mask phải rỗng → đúng
- Ảnh có defect nhưng model không detect → FN
- Ảnh không có defect nhưng model predict ra mask → FP
- Class imbalance: một số class có rất ít defect samples → cần báo cáo riêng

### 4. Chạy thử nghiệm
```bash
# Chạy đánh giá đầy đủ
python AI/evaluate/evaluate.py

# Chạy với single image để debug
python AI/evaluate/evaluate.py --single-image path/to/image.jpg --save-images

# Chạy với custom threshold
python AI/evaluate/evaluate.py --conf 0.5 --iou 0.5

# Chạy so sánh nhiều runs
python AI/evaluate/evaluate.py --compare-runs
```

## Lưu ý
- Script phải tương thích với cấu trúc dataset hiện tại (per-class subdirectories)
- Nên dùng `ultralytics` built-in validation nếu có thể (`model.val()`) để tránh implement lại metrics
- Với single image test, in ra console các thông tin: class, confidence, bounding box, mask area
- Kết quả đánh giá nên được append vào file log để theo dõi tiến trình qua các lần train
- Đảm bảo reproducibility:固定 seed khi cần so sánh kết quả giữa các lần chạy
- File plan này không quá 200 dòng