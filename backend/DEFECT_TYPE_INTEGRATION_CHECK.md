# Kiểm tra: Backend đã thực sự dùng `runs/classify/AI/defect-type/resnet18-global/weights/best.pt` chưa?

## KẾT LUẬN NGẮN GẮN
**CHƯA. File `best.pt` (resnet18-global) được định nghĩa đường dẫn và có service riêng, nhưng KHÔNG được gọi ở bất kỳ endpoint nào của `main.py`. Luồng frontend → backend hiện tại KHÔNG sử dụng mô hình phân loại defect-type này.**

## Bằng chứng từng bước

### 1. Đường dẫn được định nghĩa (`backend/config.py`)
```python
DEFECT_TYPE_MODEL_PATH = WORKSPACE_ROOT / "runs" / "classify" / "AI" / "defect-type" / "resnet18-global" / "weights" / "best.pt"
def get_defect_type_path() -> str:
    if DEFECT_TYPE_MODEL_PATH.exists():
        return str(DEFECT_TYPE_MODEL_PATH.resolve())
    return str(DEFECT_TYPE_MODEL_PATH.resolve())
```
→ Chỉ là khai báo hàm, không tự chạy.

### 2. Service tồn tại (`backend/services/defect_type_service.py`)
- `class DefectTypeService` load model qua `load_checkpoint(get_defect_type_path(), ...)` trong `__init__`.
- Có hàm `predict(image, detection, top_k)` trả về `{label, defect_type, confidence, top_k}`.
- `services/__init__.py` có export `"DefectTypeService"`.

### 3. NHƯNG không ai instantiate / gọi nó
Tìm kiếm toàn bộ `backend`:
- `DefectTypeService` chỉ xuất hiện ở:
  - `defect_type_service.py` (định nghĩa)
  - `services/__init__.py` (export)
- **KHÔNG có** `app.state.defect`, `DefectTypeService()` trong `main.py`, không có trong `lifespan`, không có trong `/detect`, `/segment`, `/inspect`, `/process_video`.

→ `main.py` chỉ khởi tạo: `YOLOService`, `CaptionService`, `VQAService`. `DefectTypeService` bị bỏ rơi.

### 4. defect_type hiện tại đến từ đâu? (heuristic, KHÔNG phải model)
Trong `FeatureExtractor._classify_defect_type` (`feature_extraction.py`):
- Dùng **từ điển cố định** `PRODUCT_DEFECT_MAP` ánh xạ `class_name` (tên lớp YOLO) → danh sách loại lỗi.
- Dựa vào **tỷ lệ khung hình polygon** (aspect ratio) để đoán `scratch/crack/cut` vs `dent/hole/chip`.
→ Đây là luật thủ công, hoàn toàn không gọi `resnet18-global/best.pt`.

### 5. Do đó luồng frontend thực tế là:
```
Frontend → /inspect (hoặc /segment, /process_video)
  → YOLOService.predict(task="segment")  → bbox + polygon + class_name
  → FeatureExtractor.extract()           → defect_type TỪ TỪ ĐIỂN (không dùng model)
  → InspectionReportService.generate_report()
  → VQAService.answer_question()
```
**Mô hình `resnet18-global/best.pt` không nằm trong chuỗi này.**

## Hậu quả
- Dù bạn đã train xong `resnet18-global`, backend vẫn trả `defect_type` theo heuristic cứng → khác với label mà model học (vd model global chỉ trả `scratch`, còn heuristic có `cracked_insulation`, `thread_defect`... không khớp).
- File `best.pt` tồn tại nhưng thành "chết" (loaded nowhere).

## Cách sửa để thực sự dùng model (nếu muốn)
1. Trong `main.py` lifespan: `app.state.defect_type = DefectTypeService(device=...)`.
2. Trong `extract()` hoặc `/inspect`, với mỗi prediction có polygon/box, gọi:
   `dt = app.state.defect_type.predict(img, detection=pred, top_k=3)` và ghi đè `item["defect_type"] = dt["defect_type"]` (giữ confidence + top_k).
3. Đảm bảo chạy backend bằng `.venv` (có torch + AI package import được).

## Lưu ý quan trọng
- `get_defect_type_path()` trả path ngay cả khi file không tồn tại (không raise). Nên nếu chưa train xong, service sẽ in "Failed to load" và `predict` trả `unknown` — an toàn nhưng vô dụng.
- Hiện tại file `resnet18-global/weights/best.pt` ĐÃ tồn tại (theo file user cung cấp), nên service SẼ load được nếu được gọi. Vấn đề chỉ là **chưa được gọi**.