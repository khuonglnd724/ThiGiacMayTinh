# Tổng quan Hệ thống Computer Vision Quality Control API
## (Reverse-engineered from codebase)

---

## 1. Mục tiêu (Goal)

Hệ thống API kiểm tra chất lượng sản phẩm công nghiệp tự động sử dụng thị giác máy tính, cho phép:
- Phát hiện và phân vùng lỗi bề mặt sản phẩm (defect detection & segmentation)
- Trích xuất đặc trưng chi tiết từng lỗi (loại lỗi, diện tích, vị trí, kích thước, mức độ nghiêm trọng) — **loại lỗi được nhận diện bởi Model 2 (ResNet18 classifier)** thay vì heuristic cứng
- Sinh báo cáo kiểm tra tự động với kết luận PASS/FLAG/REJECT
- Trả lời câu hỏi bằng ngôn ngữ tự nhiên về kết quả kiểm tra (VQA)

---

## 2. Kiến trúc tổng thể (System Architecture)

```
[Client] ──HTTP──> [FastAPI Backend]
                          │
                          ├──> [YOLO11-seg Model] ──> Raw predictions (box + mask)
                          │         │
                          │         └──> [DefectTypeService / Model 2]
                          │                   (ResNet18 classifier on ROI)
                          │                   ──> defect_type + confidence + top_k
                          │
                          ├──> Feature Extraction (area, position, size, severity)
                          ├──> Inspection Report (verdict + recommendations)
                          └──> VQA Engine
                          │
                          └──── JSON Response ────┘
```

---

## 3. Input & Output

### Input:
- File ảnh (JPEG, PNG, BMP, TIFF) tải lên qua HTTP multipart
- Tham số `conf` (confidence threshold, mặc định 0.25)
- Câu hỏi ngôn ngữ tự nhiên (cho VQA endpoint)

### Output:
- JSON response chứa:
  - Danh sách predictions đã enrich (defect_type, area, position, size, severity)
  - Ảnh đã annotate (bounding box + segmentation mask)
  - Inspection report (summary, verdict, recommendations)
  - VQA quick answers

---

## 4. Các thành phần chi tiết (Components)

### 4.1. FastAPI Application (`backend/main.py`)

Entry point của backend, định nghĩa tất cả API endpoints.

**Các route:**
| Endpoint | Method | Chức năng |
|---|---|---|
| `/` | GET | Health check server |
| `/detect` | POST | Object detection (bounding box) |
| `/segment` | POST | Segmentation (box + polygon mask) |
| `/caption` | POST | Generate image caption |
| `/vqa` | POST | Answer question về ảnh |
| `/process_video` | POST | Process video frame-by-frame |
| `/logs` | GET | Lịch sử inspection |
| `/inspect` | POST | Full pipeline: segment→extraction→report→VQA |

**Luồng xử lý chung:**
1. Nhận file upload + tham số
2. Lưu file tạm vào `uploads/`
3. Load ảnh bằng PIL, convert RGB
4. Gọi service tương ứng
5. Lưu ảnh annotate vào `static/results/`
6. Trả JSON response, xoá file tạm


### 4.2. Cấu hình (`backend/config.py`)

Quản lý paths và cấu hình hệ thống.

| Biến | Giá trị | Mô tả |
|---|---|---|
| `BASE_DIR` | `backend/` | Thư mục gốc backend |
| `UPLOAD_DIR` | `backend/uploads/` | Lưu file tạm |
| `STATIC_DIR` | `backend/static/` | Static files cho Frontend |
| `RESULTS_DIR` | `backend/static/results/` | Ảnh kết quả annotate |
| `DATABASE_PATH` | `backend/inspection.db` | SQLite database |

**Model paths:**
- `YOLO_MODEL_PATH`: `runs/segment/AI/train/runs/.../best.pt`
- `FALLBACK_YOLO_PATH`: `yolo11n-seg.pt`
- `get_yolo_path()`: Tìm best.pt trước, fallback nếu không có
- `DEFECT_TYPE_MODEL_PATH`: `runs/classify/AI/defect-type/resnet18-global/weights/best.pt` (Model 2)
- `get_defect_type_path()`: Trả path checkpoint classifier (resnet18-global); không có fallback online (nếu không load được → heuristic cũ)

---

### 4.3. Database (`backend/database.py` + `backend/models.py`)

Lưu lịch sử inspection vào SQLite qua SQLAlchemy ORM.

**Bảng `inspection_logs`:**
| Column | Type | Mô tả |
|---|---|---|
| `id` | Integer (PK) | ID tự tăng |
| `video_name` | String | Tên video |
| `frame_index` | Integer | Chỉ số frame |
| `timestamp` | Float | Thời điểm trong video |
| `has_defect` | Boolean | Có lỗi không |
| `predictions` | JSON | Predictions raw |
| `saved_image_path` | String | Đường dẫn ảnh lưu |
| `created_at` | DateTime | Thời gian tạo |

Kết nối: SQLite với `check_same_thread=False` cho phép multi-thread.

---

### 4.4. YOLO Service (`backend/services/yolo_service.py`)

**Input:** PIL Image (RGB) + confidence threshold + task ("detect"|"segment")
**Output:** `(list[predictions], np.ndarray | None)`

Mỗi prediction: `class_id`, `class_name`, `confidence`, `box`, `polygon`

**Cách hoạt động:**
1. Load model từ `best.pt` hoặc `yolo11n-seg.pt` (fallback)
2. Convert PIL -> numpy BGR cho Ultralytics
3. Gọi `model(img_bgr, conf=conf)`, parse boxes + masks
4. Extract polygon coordinates từ masks (normalized [0,1])
5. Vẽ annotated image bằng `result.plot()`


### 4.5. Defect-Type Classifier Service (`backend/services/defect_type_service.py`)

**Model 2** — Mô hình phân loại loại lỗi (defect-type classifier) ResNet18 (taxonomy `global`, ~41 lớp), checkpoint tại `runs/classify/AI/defect-type/resnet18-global/weights/best.pt`. Đây là mô hình thứ 2 trong pipeline, chuyên nhận diện **loại lỗi** (thay thế heuristic cứng trước đây).

**Input:** PIL Image (RGB) + detection (box/polygon từ YOLO) + class_name (lớp sản phẩm cha)
**Output:** `{ defect_type, confidence, top_k, constrained, class_name }`

**Cách hoạt động:**
1. Load checkpoint qua `AI/defect_type/model_utils.load_checkpoint` (PyTorch, `weights_only=False` để tránh lỗi unpickle numpy scalar trên torch>=2.6)
2. Cắt ROI theo box/polygon của detection, pad 15% biên, convert RGB
3. Chạy `predict_pil` → softmax probabilities trên `label_names` của checkpoint
4. **Ràng buộc lớp cha**: nếu `class_name` có trong `AI/defect_type/class_defect_allowed.json`, chỉ xét các label hợp lệ (ngăn model trả loại lỗi không tồn tại ở lớp đó). Nếu không có label khớp → fallback unconstrained
5. Chọn argmax (trong tập cho phép) làm `defect_type`, tính `confidence` và `top_k` (mặc định 3)
6. `_label_to_defect_type`: với taxonomy `composite` tách `class__defect` → `defect`; với `global` trả tên gốc

**Fallback an toàn:** nếu model không load được (`self.model is None`) → `predict` trả `defect_type="unknown"`, `confidence=0.0`; `FeatureExtractor` sẽ quay về heuristic `_classify_defect_type` (không crash).

**Tích hợp:** khởi tạo 1 lần trong `lifespan` (`app.state.defect_type = DefectTypeService(device="cpu")`), truyền vào `extractor.extract(...)` tại `/inspect` và `/process_video`. Endpoint `/segment` KHÔNG dùng service này (chỉ bbox/polygon).

---

### 4.6. Feature Extraction Module (`backend/services/feature_extraction.py`)

**Input:** Raw predictions từ YOLOService + image dimensions (width, height)
**Output:** Enriched predictions với 5 fields mới

| Field | Phương pháp | Output |
|---|---|---|
| **defect_type** | **Ưu tiên Model 2** (`DefectTypeService`): crop ROI → ResNet18 classifier. Nếu model null → heuristic `_classify_defect_type` (map class_name + tỉ lệ khung polygon) làm fallback | "scratch", "dent", "crack"... |
| **defect_type_confidence** | Confidence của Model 2 cho `defect_type` | 0.0 – 1.0 |
| **defect_type_topk** | Top-3 dự đoán (defect_type + confidence) của Model 2 | list |
| **defect_type_constrained** | True nếu `defect_type` bị ràng buộc bởi lớp sản phẩm cha | bool |
| **defect_type_class** | Lớp sản phẩm cha (class_name) truyền vào Model 2 | str |
| **area** | Shoelace formula: `0.5 * \|Σ(xi*yj - xj*yi)\|` | px, normalized, % |
| **position** | 9-zone grid + centroid computation | zone + mô tả |
| **size_classification** | Threshold trên % diện tích ảnh | micro->critical (6 levels) |
| **severity** | Score 0-100: area(40) + position(30) + confidence(30) | Low/Medium/High/Critical |

**PRODUCT_DEFECT_MAP:** (FALLBACK) Map 16 product classes (bottle, cable...) to candidate defect types — chỉ dùng khi Model 2 không khả dụng (`_classify_defect_type`)

**Severity scoring:** Area: `40*(1-e^(-area*50))` + Position: center=30/edge=10 + Confidence: `30*conf` => <25 Low / 25-50 Medium / 50-75 High / >75 Critical


### 4.7. Inspection Report Service (`backend/services/inspection_report.py`)

**Input:** Enriched predictions + filename + image size
**Output:** Structured report với verdict (PASS|FLAG|REJECT) + recommendations

Cấu trúc: `inspection_summary` + `position_analysis` + `verdict` + `recommendations`

**Verdict logic (rule-based):**
1. Có High/Critical severity -> **REJECT**
2. Không defect -> **PASS**
3. >2 Medium -> **REJECT**
4. 1-2 Medium -> **FLAG** (secondary inspection)
5. All Low -> **PASS**

---

### 4.8. VQA Service (`backend/services/vqa_service.py`)

**Input:** PIL Image + question + optional inspection_context
**Output:** Answer string

**3 modes (priority):**
1. **Context-aware**: Dùng inspection report để trả lời (defect, severity, position, verdict, recs)
2. **Transformers**: `dandelin/vilt-b32-finetuned-vqa`
3. **Keyword fallback**: Simple keyword matching

---

### 4.9. Caption Service (`backend/services/caption_service.py`)

**Input:** PIL Image | **Output:** String caption
- Mode 1: `Salesforce/blip-image-captioning-base`
- Mode 2: Mock fallback text

---

## 5. Luồng xử lý `/inspect` endpoint (Flow)

```
[Upload Image] -> [YOLO11-seg] -> Raw predictions (box + mask)
  -> [DefectTypeService / Model 2] -> defect_type (+ confidence, top_k) từ ROI
  -> [FeatureExtractor] -> area, position, size, severity (defect_type ưu tiên từ Model 2)
  -> [InspectionReport] -> summary, verdict, recommendations
  -> [VQA] -> 5 quick answers
  -> [Final JSON Response] -> enriched predictions + report + VQA
```

---

## 6. Files trong dự án

| File | Vai trò |
|---|---|
| `backend/main.py` | FastAPI app + endpoints |
| `backend/config.py` | Paths, database, model paths |
| `AI/defect_type/model_utils.py` | Load checkpoint + inference cho Model 2 (ResNet18) |
| `backend/database.py` | SQLAlchemy engine |
| `backend/models.py` | InspectionLog model |
| `services/yolo_service.py` | YOLO inference |
| `services/feature_extraction.py` | Enrich predictions |
| `services/inspection_report.py` | QC report |
| `services/vqa_service.py` | Visual QA |
| `services/caption_service.py` | Captioning |
| `services/defect_type_service.py` | Model 2: phân loại defect-type (ResNet18 classifier) |

---

## 7. Tech Stack

| Công nghệ | Mục đích |
|---|---|
| FastAPI / Uvicorn | Web server |
| SQLAlchemy / SQLite | Database |
| Ultralytics YOLO | Detection + Segmentation |
| Transformers (BLIP, VILT) | Captioning + VQA |
| PyTorch | Deep learning (YOLO + ResNet18 classifier) |
| TorchVision ResNet18 | Model 2: defect-type classification |
| OpenCV / Pillow | Image processing |

---

## 8. Lưu ý (Notes)

- Services khởi tạo 1 lần khi startup (lifespan) -> cache trong `app.state`
- File tạm xoá sau mỗi request (finally block)
- YOLO fallback: best.pt -> yolo11n-seg.pt -> online download
- Defect-type model (Model 2) fallback: nếu `best.pt` classifier không load được → `defect_type` quay về heuristic `_classify_defect_type` (PRODUCT_DEFECT_MAP), không crash
- CORS allow all origins (cần restrict production)
- Ảnh kết quả lưu tại `static/results/` -> Frontend truy cập qua `/static/`
