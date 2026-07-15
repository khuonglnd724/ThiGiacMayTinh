# Computer Vision Quality Control API

Hệ thống kiểm tra chất lượng sản phẩm công nghiệp tự động bằng **Thị giác máy tính (Computer Vision)**. Kết hợp hai mô hình deep learning:

- **Model 1 — YOLO11-seg**: Phát hiện và phân vùng (segmentation) các lỗi bề mặt sản phẩm.
- **Model 2 — DefectTypeService (ResNet18 classifier)**: Nhận diện **loại lỗi** (scratch, crack, dent, ...) từ vùng ảnh lỗi (ROI), thay thế heuristic cứng trước đây.

Hệ thống cung cấp API (FastAPI) đầy đủ pipeline: detect → segment → phân loại loại lỗi → trích xuất đặc trưng → báo cáo PASS/FLAG/REJECT → trả lời câu hỏi (VQA), kèm giao diện web (Frontend) để vận hành.

---

## 📑 Mục lục

- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Tính năng chính](#tính-năng-chính)
- [Kiến trúc & Hai mô hình](#kiến-trúc--hai-mô-hình)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt](#cài-đặt)
- [Chạy dự án](#chạy-dự-án)
- [API Endpoints](#api-endpoints)
- [Huấn luyện mô hình](#huấn-luyện-mô-hình)
- [Đánh giá (Evaluation)](#đánh-giá-evaluation)
- [Tài liệu & Nhật ký](#tài-liệu--nhật-ký)
- [Ghi chú quan trọng](#ghi-chú-quan-trọng)

---

## Cấu trúc dự án

```
ThiGiacMayTinh/
├── backend/                      # FastAPI backend + AI services
│   ├── main.py                   # Entry point, định nghĩa endpoints, lifespan
│   ├── config.py                 # Paths, database, model paths
│   ├── database.py               # SQLAlchemy engine + session
│   ├── models.py                 # ORM model InspectionLog
│   ├── services/
│   │   ├── yolo_service.py       # Model 1: YOLO11-seg inference
│   │   ├── defect_type_service.py# Model 2: ResNet18 defect-type classifier
│   │   ├── feature_extraction.py # Enrich predictions (area, position, size, severity)
│   │   ├── inspection_report.py  # Sinh báo cáo PASS/FLAG/REJECT
│   │   ├── vqa_service.py        # Visual Question Answering
│   │   └── caption_service.py    # Image captioning (BLIP)
│   ├── static/results/           # Ảnh annotate kết quả
│   ├── uploads/                  # File tạm
│   └── inspection.db             # SQLite database
│
├── frontend/                     # Giao diện web (HTML/CSS/JS thuần)
│   ├── index.html
│   ├── css/  (style.css, responsive.css)
│   └── js/   (app.js, api.js, ui.js, utils.js)
│
├── AI/                           # Pipeline huấn luyện & tiền xử lý
│   ├── dataset/                  # Tải dataset (MVTec AD), download script
│   ├── preprocess/              # Tiền xử lý, crop ROI theo mask
│   ├── train/                    # Huấn luyện YOLO segmentation (data.yaml, train.py)
│   └── defect_type/             # Huấn luyện Model 2 (ResNet18 classifier)
│       ├── train.py, dataset.py, model_utils.py
│       └── class_defect_allowed.json  # Ràng buộc lớp cha → loại lỗi
│
├── runs/                         # Checkpoints đã huấn luyện
│   ├── segment/AI/.../weights/best.pt     # Model 1
│   └── classify/AI/defect-type/resnet18-global/weights/best.pt  # Model 2
│
├── test/                         # Script đánh giá & benchmark
│   ├── evaluate.py               # Đánh giá Model 1 (YOLO segmentation)
│   ├── evaluate_defect_type.py   # Đánh giá Model 2 (defect-type classifier)
│   ├── evaluate_e2e_pipeline.py  # Đánh giá end-to-end pipeline
│   ├── analyze_report.py         # Phân tích báo cáo inspection
│   └── output*/                  # Kết quả đánh giá
│
├── docs/                         # Tài liệu & kế hoạch
│   ├── plan/system_overview.md   # Tổng quan hệ thống (reverse-engineered)
│   ├── plan/backend_api.md       # Chi tiết API
│   └── rule.md, description/...
│
├── log/                          # Nhật ký phát triển & tích hợp
└── requirements.txt
```

---

## Tính năng chính

- **Phát hiện & phân vùng lỗi** (Model 1, YOLO11-seg): bounding box + polygon mask.
- **Nhận diện loại lỗi** (Model 2, ResNet18): scratch, crack, dent, bent, ... lấy từ ROI của từng detection, có ràng buộc theo lớp sản phẩm cha.
- **Trích xuất đặc trưng**: diện tích (Shoelace), vị trí (9-zone grid), phân loại kích thước (6 mức), điểm mức độ nghiêm trọng (Low/Medium/High/Critical).
- **Báo cáo kiểm tra tự động**: tóm tắt + verdict (PASS/FLAG/REJECT) + khuyến nghị.
- **VQA**: trả lời câu hỏi tự nhiên về ảnh dựa trên kết quả inspection.
- **Xử lý video**: chạy frame-by-frame với frame skip rate.
- **Lịch sử**: lưu mọi inspection vào SQLite, xem / lọc / xoá qua frontend.
- **Giao diện web**: Dashboard, Upload & Inspect, Results, History, Settings (Dark/Light mode, lưu LocalStorage).

---

## Kiến trúc & Hai mô hình

```
[Client] ──HTTP──> [FastAPI Backend]
                        │
                        ├──> [Model 1: YOLO11-seg] ──> Raw predictions (box + mask)
                        │         │
                        │         └──> [Model 2: DefectTypeService / ResNet18]
                        │                   crop ROI → classifier → defect_type + conf + top_k
                        │
                        ├──> Feature Extraction (area, position, size, severity)
                        ├──> Inspection Report (verdict + recommendations)
                        └──> VQA Engine
                        │
                        └──── JSON Response ────┘
```

**Model 1 (YOLO Service — `backend/services/yolo_service.py`)**
- Mô hình: **YOLO11-seg** (Ultralytics) — đồng thời làm detection & instance segmentation.
- Checkpoint: `runs/segment/AI/train/runs/ai-segmentation/segmentation-yolo11n-27-6-23h/weights/best.pt` (fallback `yolo11n-seg.pt`, sau đó online download).
- **Input**: PIL Image (RGB) + confidence threshold (`conf`, mặc định 0.25) + task (`detect`|`segment`).
- **Cách hoạt động**:
  1. Load model từ `best.pt` hoặc `yolo11n-seg.pt` (fallback).
  2. Convert PIL → numpy BGR cho Ultralytics.
  3. Gọi `model(img_bgr, conf=conf)`, parse boxes + masks.
  4. Extract polygon coordinates từ masks (normalized [0,1]).
  5. Vẽ annotated image bằng `result.plot()`.
- **Output**: `(list[predictions], np.ndarray | None)` — mỗi prediction gồm `class_id`, `class_name`, `confidence`, `box`, `polygon`.
- Là mô hình **đầu tiên** trong pipeline, cung cấp raw predictions (box + mask) làm đầu vào cho Model 2 và Feature Extraction.

**Model 2 (DefectTypeService)**
- Checkpoint: `runs/classify/AI/defect-type/resnet18-global/weights/best.pt` (taxonomy `global`, ~41 lớp).
- Load qua `AI/defect_type/model_utils.load_checkpoint` (PyTorch, `weights_only=False` để tương thích torch ≥ 2.6).
- Cắt ROI theo box/polygon (pad 15% biên), chạy `predict_pil` → softmax.
- **Ràng buộc lớp cha**: nếu `class_name` có trong `AI/defect_type/class_defect_allowed.json`, chỉ xét các label hợp lệ → ngăn model trả loại lỗi không tồn tại ở lớp đó.
- **Fallback an toàn**: nếu checkpoint không load được → `defect_type` quay về heuristic `_classify_defect_type` (PRODUCT_DEFECT_MAP), không crash.

---

## Yêu cầu hệ thống

- Python ≥ 3.9
- pip
- (Tùy chọn) GPU CUDA cho tăng tốc; mặc định chạy CPU.
- Trình duyệt hiện đại (Chrome/Firefox/Edge/Safari) cho frontend.

Dependencies chính (`requirements.txt`):
`fastapi`, `uvicorn`, `sqlalchemy`, `python-multipart`, `ultralytics`, `torch`, `torchvision`, `transformers`, `opencv-python`, `pillow`, `numpy`.

---

## Cài đặt

```bash
# 1. (Khuyến nghị) Tạo virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Cài đặt dependencies
pip install -r requirements.txt
```

> **Lưu ý model weights**: Đảm bảo các file checkpoint tồn tại:
> - Model 1: `runs/segment/AI/train/runs/ai-segmentation/segmentation-yolo11n-27-6-23h/weights/best.pt` (fallback `yolo11n-seg.pt`).
> - Model 2: `runs/classify/AI/defect-type/resnet18-global/weights/best.pt`.
> Nếu thiếu, backend tự fallback (YOLO → `yolo11n-seg.pt` online; DefectType → heuristic cũ).

---

## Chạy dự án

### 1. Backend (Terminal 1)

```bash
cd backend
python main.py
```

Backend chạy trên **http://localhost:8000** (Swagger docs tại `/docs`).

### 2. Frontend (Terminal 2)

```bash
# Option A: Python
cd frontend
python -m http.server 3000 --directory .

# Option B: Node.js
cd frontend
npx http-server . -p 3000
```

Truy cập **http://localhost:3000**.

### Workflow ví dụ
1. Mở **Dashboard** xem thống kê.
2. Vào **Upload & Inspect**, kéo thả ảnh (JPEG/PNG/BMP/TIFF) hoặc video.
3. Chỉnh Confidence Threshold (mặc định 0.25) → **Start Inspection**.
4. Xem ảnh annotate, danh sách lỗi, báo cáo, VQA answers.
5. Vào **History** lọc theo PASS/FLAG/REJECT, xem/xoá bản ghi.

---

## API Endpoints

| Endpoint | Method | Chức năng |
|---|---|---|
| `/` | GET | Health check |
| `/detect` | POST | Object detection (bounding box) |
| `/segment` | POST | Segmentation (box + polygon mask) |
| `/caption` | POST | Sinh mô tả ảnh (BLIP) |
| `/vqa` | POST | Trả lời câu hỏi về ảnh |
| `/process_video` | POST | Xử lý video frame-by-frame |
| `/logs` | GET | Lịch sử inspection (SQLite) |
| `/inspect` | POST | **Full pipeline**: segment → Model 2 (defect type) → feature extraction → report → VQA |

**Ví dụ response `/inspect`** (mỗi prediction enriched):
```json
{
  "predictions": [{
    "defect_type": "scratch",
    "defect_type_confidence": 0.91,
    "defect_type_topk": [{"defect_type": "scratch", "confidence": 0.91}, ...],
    "defect_type_constrained": true,
    "defect_type_class": "bottle",
    "confidence": 0.97,
    "area": {"polygon_area_percent": 1.23, ...},
    "position": {"zone": "top-left", ...},
    "size_classification": {"level": "small", ...},
    "severity": {"score": 62.4, "level": "High", ...}
  }],
  "annotated_image_path": "/static/results/...png",
  "report": {"verdict": "REJECT", "summary": "...", "recommendations": [...]},
  "vqa_answers": {"Có lỗi không?": "Có, phát hiện 1 lỗi", ...}
}
```

Chi tiết tham số từng endpoint xem tại `docs/plan/backend_api.md`.

---

## Huấn luyện mô hình

### Model 1 — YOLO Segmentation
```bash
# Tải dataset MVTec AD
python AI/dataset/download_mvtec.py

# Tiền xử lý
python AI/preprocess/preprocess.py

# Huấn luyện
python AI/train/train.py
```
Cấu hình data tại `AI/train/data.yaml`; checkpoint xuất ra `runs/segment/...`.

### Model 2 — Defect-Type Classifier (ResNet18)
```bash
# Chuẩn bị dataset phân loại loại lỗi
python AI/defect_type/prepare_dataset.py

# Huấn luyện (resnet18-global)
python AI/defect_type/train.py
```
Checkpoint xuất ra `runs/classify/AI/defect-type/resnet18-global/weights/best.pt`.
Ràng buộc lớp cha (`class_defect_allowed.json`) được sinh tự động từ manifest tập train.

---

## Đánh giá (Evaluation)

| Script | Mục đích |
|---|---|
| `test/evaluate.py` | Benchmark Model 1 (YOLO segmentation): mAP, mask metrics... |
| `test/evaluate_defect_type.py` | Benchmark Model 2: Accuracy, Top-2, Macro/Micro P/R/F1, per-class, confusion matrix. Hỗ trợ `--constrained`, `--compare-runs`, `--single-image`, `--save-cm`. |
| `test/evaluate_e2e_pipeline.py` | Đánh giá toàn bộ pipeline end-to-end. |
| `test/analyze_report.py` | Phân tích báo cáo inspection. |

**Ví dụ:**
```bash
# Đánh giá Model 2 (raw)
python test/evaluate_defect_type.py --device cpu

# Đánh giá Model 2 có ràng buộc lớp cha (giống deployment)
python test/evaluate_defect_type.py --constrained --device cpu

# Lưu confusion matrix
python test/evaluate_defect_type.py --save-cm --device cpu
```
Kết quả xuất ra `test/output_defect_type/`, `test/output/`, `test/output_e2e_pipeline/`.

---

## Tài liệu & Nhật ký

- `docs/plan/system_overview.md` — Tổng quan hệ thống (reverse-engineered từ code).
- `docs/plan/backend_api.md` — Chi tiết API.
- `docs/plan/plan_test_evaluate_model2_defect_type.md` — Kế hoạch đánh giá Model 2.
- `QUICK_START.md` — Hướng dẫn nhanh frontend.
- `frontend/README.md` — Chi tiết giao diện web.
- `log/` — Nhật ký phát triển & tích hợp (vd. `integrate_defect_type_model_log.md`).

---

## Ghi chú quan trọng

- **Services khởi tạo 1 lần** khi startup (`lifespan`) và cache trong `app.state`.
- **Fallback**:
  - YOLO: `best.pt` → `yolo11n-seg.pt` → online download.
  - Defect-type: nếu checkpoint null → heuristic `_classify_defect_type` (PRODUCT_DEFECT_MAP).
- **CORS**: backend cho phép tất cả origin (`allow_origins=["*"]`); nên thu hẹp khi deploy production.
- **Lưu trữ**: ảnh kết quả tại `backend/static/results/` (truy cập `/static/`), lịch sử tại `inspection.db`.
- **Torch ≥ 2.6**: checkpoint Model 2 load với `weights_only=False` để tránh lỗi unpickle numpy scalar.

---
