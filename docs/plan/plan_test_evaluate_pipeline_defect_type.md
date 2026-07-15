# Plan: Test & Evaluate Pipeline Model 1 -> Model 2 (End-to-End)

## Goal
Bổ sung một bản đánh giá **pipeline** tách biệt với bản đánh giá **model** thuần
(`test/evaluate_defect_type.py` chỉ crop ROI từ ground-truth mask). Bản pipeline
chạy toàn bộ chuỗi thực tế để đo hiệu năng end-to-end và tách biệt lỗi do bước
segmentation (Model 1) gây ra:

    Model 1 (YOLO segmentation) -> mask dự đoán -> crop ROI -> Model 2 (classifier)

So sánh end-to-end với baseline dùng GT mask để thấy pipeline làm giảm bao nhiêu,
đồng thời báo cáo chẩn đoán pipeline (mask IoU pred vs GT, tỉ lệ bỏ sót defect).

## Input
- **Model 1 (segmentation)**: `runs/segment/AI/train/runs/ai-segmentation/segmentation/weights/best.pt` (default), load qua `ultralytics.YOLO`.
- **Model 2 (classifier)**: `runs/classify/AI/defect-type/resnet18-global/weights/best.pt` (default), load qua `load_checkpoint`.
- **Preprocess root**: `AI/preprocess/output` (chứa `images/test/{class}/*.jpg` gốc + `masks/test/{class}/*.png` GT, dùng để lấy GT label & GT mask).
- **CLI**:
  - `--seg-model`, `--cls-model`
  - `--preprocess-root`, `--taxonomy` (`global`|`composite`)
  - `--image-size` (ROI size Model 2), `--batch`
  - `--device` (`auto`|`cpu`|`cuda`)
  - `--constrained` (ràng buộc lớp cha cho Model 2)
  - `--output-dir` (mặc định `test/output_e2e_pipeline`)
  - `--seg-conf`, `--seg-iou`, `--seg-imgsz` (tham số Model 1)
  - `--save-cm` (lưu confusion matrix PNG)

## Output
- **JSON**: `{output_dir}/pipeline_evaluation_report.json`
  - `config`: path 2 model, seg_conf/iou/imgsz, device, constrained.
  - `end_to_end`: metrics phân loại chạy trên ROI từ mask dự đoán (accuracy, top2, macro/micro P/R/F1, per_class, confusion_matrix, pipeline_diagnostics).
  - `baseline_gt_mask`: metrics tương ứng khi crop từ GT mask (tách riêng năng lực Model 2).
  - `drop_vs_baseline`: hiệu số (end-to-end - baseline) cho accuracy/top2/macro_f1.
- **CSV**: `{output_dir}/pipeline_per_class_metrics.csv` (per-class end-to-end).
- **PNG**: `pipeline_confusion_matrix.png` (có lớp `<missed/no_mask>`) và `baseline_confusion_matrix.png` (nếu `--save-cm`).

## How to do

### 1. Tái sử dụng module
- Mask helpers từ `test/evaluate.py`: `decode_mask_from_result`, `load_ground_truth_mask`, `compute_mask_metrics`.
- Classifier helpers từ `test/evaluate_defect_type.py`: `apply_constraint`, `compute_metrics`, `evaluate_test_set` (dùng chạy baseline GT-mask), `load_allowed_map`.
- Dataset: `discover_defect_samples`, `split_samples_by_label`, `crop_roi_with_mask`; model: `build_image_transform`, `load_checkpoint`.

### 2. Load 2 model
- Model 1: `YOLO(seg_model_path)`.
- Model 2: `load_checkpoint(cls_model_path, device)`. Lấy `label_names`, `image_size`, `taxonomy`.

### 3. Baseline (dùng GT mask)
- `evaluate_test_set(Model2, metadata, test_samples, cls_config)` -> crop ROI từ **GT mask** (như bản model thuần). Kết quả là năng lực Model 2 tách biệt.

### 4. End-to-end pipeline
- Với mỗi test sample:
  - Mở ảnh gốc; load GT mask để tính diagnostics.
  - Chạy Model 1 `predict` trên ảnh gốc -> `decode_mask_from_result` ra predicted mask (kích thước ảnh gốc).
  - Tính **mask IoU** (pred vs GT) nếu có predicted mask; nếu không có mask -> đếm `missed_by_segmentation`.
  - Nếu có predicted mask: build mask PIL (0/255) -> `crop_roi_with_mask` (padding 0.18, blend) -> ROI -> Model 2 -> softmax -> `apply_constraint` (nếu `--constrained`) -> predicted label.
  - Nếu không có mask: dự đoán = lớp giả `<missed/no_mask>` (index = num_classes) để đưa vào confusion matrix.
- Gom predictions/targets, gọi `compute_metrics` với `label_names + ["<missed/no_mask>"]`.

### 5. Báo cáo & so sánh
- Ghi JSON/CSV; vẽ 2 confusion matrix nếu `--save-cm`.
- In tóm tắt: mean mask IoU, missed rate, và bảng end-to-end vs baseline (accuracy/top2/macro_f1 + drop).

## Cách chạy chi tiết (CLI reference)

Tất cả lệnh chạy từ thư mục gốc dự án (`d:/TGMT/ThiGiacMayTinh`):

```bash
# 1. End-to-end + so sánh baseline GT-mask
python test/evaluate_e2e_pipeline.py --device cpu

# 2. Có ràng buộc lớp cha (giống deployment)
python test/evaluate_e2e_pipeline.py --constrained --device cpu

# 3. Lưu 2 confusion matrix (pipeline + baseline)
python test/evaluate_e2e_pipeline.py --save-cm --device cpu

# 4. Tuỳ chỉnh ngưỡng Model 1
python test/evaluate_e2e_pipeline.py --seg-conf 0.3 --seg-iou 0.5 --device cpu

# 5. Đổi checkpoint Model 1 / Model 2
python test/evaluate_e2e_pipeline.py \
    --seg-model runs/segment/AI/train/runs/ai-segmentation/segmentation/weights/best.pt \
    --cls-model runs/classify/AI/defect-type/mobilenet_v3_small-global/weights/best.pt \
    --device cpu
```

**Kết quả sinh ra** (trong `--output-dir`, mặc định `test/output_e2e_pipeline`):
- `pipeline_evaluation_report.json` – end_to_end + baseline_gt_mask + drop_vs_baseline + pipeline_diagnostics.
- `pipeline_per_class_metrics.csv` – per-class end-to-end (có lớp `<missed/no_mask>`).
- `pipeline_confusion_matrix.png`, `baseline_confusion_matrix.png` – chỉ khi `--save-cm`.

## Lưu ý
- Bản **model** (`test/evaluate_defect_type.py`) đo năng lực thuần của Model 2 (crop từ GT mask) -> KHÔNG dùng mask dự đoán.
- Bản **pipeline** này dùng Model 1 sinh mask dự đoán -> đo end-to-end, bao gồm cả lỗi segmentation.
- `decode_mask_from_result` trả về mask đã resize về kích thước ảnh gốc, khớp với `load_ground_truth_mask` để tính IoU.
- Giữ seed = 42 để tách test split nhất quán với lúc train và với bản model.
- File plan không quá 200 dòng.