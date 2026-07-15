# Plan: Test & Evaluate Model 2 (Defect-Type Classifier)

## Goal
Xây dựng script `test/evaluate_defect_type.py` để benchmark model thứ 2 (classifier phân loại loại lỗi / defect type) đã huấn luyện, tương đương với `test/evaluate.py` dành cho model 1 (YOLO segmentation). Script cho phép:
- Chạy inference trên toàn bộ tập test của defect-type classifier.
- Tính toán metrics phân loại: Accuracy, Top-2 Accuracy, Macro/Micro Precision, Recall, F1.
- Báo cáo per-class (Precision, Recall, F1, support) và Confusion Matrix.
- Hỗ trợ đánh giá ở cả chế độ raw (không ràng buộc) và chế độ constrained (áp dụng ràng buộc lớp cha từ `class_defect_allowed.json`, giống `DefectTypeService`).
- So sánh nhiều run (architecture/taxonomy khác nhau) trong `runs/classify/AI/defect-type/`.
- Debug nhanh trên single image.
- Xuất báo cáo JSON / CSV kèm confusion matrix image.

## Input
- **Model checkpoint**: `runs/classify/AI/defect-type/<arch>-<taxonomy>/weights/best.pt` (mặc định: `resnet18-global`). Checkpoint chứa `architecture`, `taxonomy`, `image_size`, `label_names`, `state_dict`.
- **Preprocess root**: `AI/preprocess/output` chứa `images/{split}/{class}/` và `masks/{split}/{class}/`. Tên file mask có dạng `test_<defect_type>__<source_stem>.png`.
- **Constraint map**: `AI/defect_type/class_defect_allowed.json` (lớp sản phẩm -> danh sách defect type hợp lệ).
- **Tham số CLI**:
  - `--model`: path checkpoint (mặc định best.pt của resnet18-global).
  - `--preprocess-root`: root preprocess (mặc định `AI/preprocess/output`).
  - `--taxonomy`: `composite` | `global` (mặc định `global`, dùng để phát hiện test samples & giải mã label).
  - `--image-size`: kích thước ROI đưa vào model (lấy từ checkpoint nếu không truyền).
  - `--batch`: batch size (mặc định 32).
  - `--device`: `auto` | `cpu` | `cuda` (mặc định `auto`).
  - `--constrained`: flag đánh giá có áp dụng ràng buộc lớp cha (giống deployment).
  - `--output-dir`: thư mục lưu kết quả (mặc định `test/output_defect_type`).
  - `--single-image`: path ảnh để debug (optional, kèm `--class-name`).
  - `--class-name`: lớp sản phẩm cha khi chạy single image / constrained.
  - `--save-cm`: lưu confusion matrix image.
  - `--compare-runs`: so sánh nhiều run trong `runs/classify/AI/defect-type/`.

## Output
- **Báo cáo JSON**: `{output_dir}/defect_type_evaluation_report.json` gồm config, global metrics (accuracy, top2_accuracy, macro_precision/recall/f1, micro metrics), per_class, confusion_matrix.
- **Báo cáo per-class CSV**: `{output_dir}/defect_type_per_class_metrics.csv`.
- **Confusion matrix PNG**: `{output_dir}/confusion_matrix.png` (nếu `--save-cm`).
- **Báo cáo so sánh run**: `{output_dir}/comparison/run_comparison.csv|json` (nếu `--compare-runs`).
- **Log tóm tắt** in ra console.

## How to do

### 1. Tái sử dụng module có sẵn
- Import từ `AI.defect_type.dataset`: `discover_defect_samples`, `split_samples_by_label`, `crop_roi_with_mask`.
- Import từ `AI.defect_type.model_utils`: `load_checkpoint`, `build_image_transform`, `make_label_display`, `top_k_predictions`.
- Đây là cùng pipeline dùng lúc train nên đảm bảo nhất quán tiền xử lý ROI (crop theo mask + padding 0.18 + blend background).

### 2. Thu thập test samples
- `all_samples = discover_defect_samples(preprocess_root, taxonomy, split=None)`.
- `split_samples_by_label(all_samples, seed=42)` -> lấy `test_samples`.
- Ground-truth label của mỗi sample là `sample.label` (= `defect_type` với taxonomy global, `class__defect_type` với composite). `sample.class_name` là lớp sản phẩm cha.

### 3. Load model
- `model, metadata = load_checkpoint(model_path, device)`. Lấy `label_names`, `image_size`, `taxonomy` từ metadata.
- Nếu người dùng truyền `--image-size` thì ưu tiên giá trị đó cho transform.

### 4. Chạy inference & tính metrics
- Với mỗi test sample: mở ảnh + mask, `crop_roi_with_mask` -> ROI PIL, transform -> tensor, `model(tensor)` -> softmax probs.
- **Chế độ constrained**: nếu `--constrained`, nạp `class_defect_allowed.json`, chỉ giữ các label thuộc `allowed_map[class_name]`, chọn argmax trong tập cho phép. Logic y hệt `DefectTypeService.predict`.
- **Chế độ raw**: argmax trên toàn bộ `label_names`.
- Gom logits/targets, tính:
  - `accuracy = correct/total`
  - `top2_accuracy`: target nằm trong top-2 probs.
  - Per-class TP/FP/FN -> Precision/Recall/F1, support.
  - `macro_* = mean(per_class)`.
  - Confusion matrix (num_classes x num_classes).

### 5. Báo cáo & visualization
- Ghi JSON, CSV. Vẽ confusion matrix bằng matplotlib (Agg backend) nếu `--save-cm`.
- In tóm tắt: accuracy, top2, macro F1, rồi từng dòng per-class.

### 6. So sánh nhiều run (`--compare-runs`)
- Duyệt `runs/classify/AI/defect-type/*/weights/best.pt`, load từng model, chạy đánh giá trên chung 1 test set, gom accuracy/macro_f1 vào bảng CSV/JSON.

### 7. Single image (`--single-image`)
- Mở ảnh, nếu có `--class-name` thì crop toàn bộ ảnh (không có mask) rồi predict; in ra top-k predictions + defect_type (dùng `make_label_display`).

## Cách chạy chi tiết (CLI reference)

Tất cả lệnh chạy từ thư mục gốc dự án (`d:/TGMT/ThiGiacMayTinh`):

```bash
# 1. Đánh giá đầy đủ (raw, không ràng buộc) trên checkpoint mặc định resnet18-global
python test/evaluate_defect_type.py --device cpu

# 2. Đánh giá có ràng buộc lớp cha (giống deployment qua DefectTypeService)
python test/evaluate_defect_type.py --constrained --device cpu

# 3. Lưu confusion matrix ảnh PNG (thêm vào bước 1 hoặc 2)
python test/evaluate_defect_type.py --save-cm --device cpu
python test/evaluate_defect_type.py --constrained --save-cm --device cpu

# 4. Đánh giá 1 checkpoint khác (ví dụ mobilenet_v3_small, taxonomy global)
python test/evaluate_defect_type.py \
    --model runs/classify/AI/defect-type/mobilenet_v3_small-global/weights/best.pt \
    --device cpu

# 5. Đánh giá taxonomy composite (nếu có checkpoint composite)
python test/evaluate_defect_type.py --taxonomy composite --device cpu

# 6. Tuỳ chỉnh image size / batch (nếu checkpoint dùng kích thước khác)
python test/evaluate_defect_type.py --image-size 224 --batch 64 --device cpu

# 7. So sánh nhiều run (tất cả best.pt trong runs/classify/AI/defect-type/*)
python test/evaluate_defect_type.py --compare-runs --device cpu
python test/evaluate_defect_type.py --compare-runs --constrained --device cpu

# 8. Debug nhanh 1 ảnh (dùng whole image làm ROI)
python test/evaluate_defect_type.py --single-image path/to/roi.jpg --device cpu
python test/evaluate_defect_type.py --single-image path/to/roi.jpg --class-name bottle --constrained --device cpu

# 9. Đổi thư mục lưu kết quả
python test/evaluate_defect_type.py --output-dir test/output_defect_type_v2 --device cpu
```

**Giải thích tham số:**
- `--device`: `auto` (mặc định, tự chọn cuda nếu có) | `cpu` | `cuda`. Dùng `cpu` khi máy không có GPU.
- `--constrained`: bật ràng buộc chỉ cho phép các defect type hợp lệ của lớp sản phẩm (từ `class_defect_allowed.json`). Tắt = đánh giá năng lực thô của model.
- `--taxonomy`: phải khớp với checkpoint (`global` hay `composite`) để discover đúng ground-truth.
- `--compare-runs`: chạy tuần tự từng `best.pt` trong `runs/classify/AI/defect-type/` trên chung 1 test set, xuất bảng so sánh.
- `--single-image`: chỉ chạy trên 1 ảnh, in top-5 dự đoán; không dùng mask nên crop = whole image.

**Kết quả sinh ra** (trong `--output-dir`, mặc định `test/output_defect_type`):
- `defect_type_evaluation_report.json` – metrics tổng + per_class + confusion matrix.
- `defect_type_per_class_metrics.csv` – bảng per-class.
- `confusion_matrix.png` – chỉ khi `--save-cm`.
- `comparison/run_comparison.csv|json` – chỉ khi `--compare-runs`.

## Lưu ý
- Phải dùng đúng `crop_roi_with_mask` (crop theo mask + blend background) để khớp với lúc train; không predict trên whole image trừ chế độ single-image không có mask.
- Taxonomy `global` dùng label = `defect_type`; `composite` dùng `class__defect_type`. Phải truyền đúng `--taxonomy` khớp với checkpoint để discover đúng ground-truth.
- Khi đánh giá constrained, class_name lấy từ `sample.class_name`; nếu class không có trong map thì fallback sang unconstrained (giống service).
- Giữ seed = 42 để tách test split nhất quán với lúc train.
- File plan không quá 200 dòng.