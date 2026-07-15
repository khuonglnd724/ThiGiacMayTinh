# Log: Tích hợp mô hình phân loại defect-type (resnet18-global) vào backend

**Ngày:** 2026-07-15
**Plan tham chiếu:** `docs/plan/integrate_defect_type_model.md`
**File liên quan:** `backend/main.py`, `backend/services/feature_extraction.py`

---

## Mục tiêu
Thay thế suy luận `defect_type` bằng heuristic cứng (`FeatureExtractor._classify_defect_type`)
bằng mô hình đã huấn luyện `runs/classify/AI/defect-type/resnet18-global/weights/best.pt`
(classifier ResNet18, taxonomy `global`) thông qua `DefectTypeService`.

---

## Các thay đổi đã thực hiện

### 1. `backend/services/feature_extraction.py`
- **Sửa hàm `FeatureExtractor.extract`**:
  - Thêm 2 tham số mới: `defect_type_service: Any | None = None` và `img: Any | None = None`.
  - Với mỗi prediction: nếu `defect_type_service` không None, `service.model` không None, và `img` không None
    → gọi `defect_type_service.predict(img, detection=pred, top_k=3)` và gán:
    - `item["defect_type"] = dt["defect_type"]`
    - `item["defect_type_confidence"] = dt["confidence"]`
    - `item["defect_type_topk"] = dt["top_k"]`
  - Ngược lại giữ heuristic cũ (`_classify_defect_type`) làm fallback an toàn.
  - Cập nhật docstring mô tả 2 tham số mới.
- **Giữ nguyên** `_classify_defect_type` (không xóa) làm fallback.

### 2. `backend/main.py`
- **Import**: thêm `from .services.defect_type_service import DefectTypeService` (và nhánh `except ImportError`).
- **Lifespan**: trong `lifespan(app)`, sau khi tạo `yolo/caption/vqa`, thêm:
  `app.state.defect_type = DefectTypeService(device="cpu")`.
- **Endpoint `/inspect`**: truyền `defect_type_service=app.state.defect_type, img=img` vào
  `extractor.extract(...)`.
- **Endpoint `/process_video`**: chuyển frame BGR→RGB PIL (`frame_rgb_pil`) và truyền
  `defect_type_service=app.state.defect_type, img=frame_rgb_pil` vào `extractor.extract(...)`.
- Endpoint `/segment` giữ nguyên (chỉ trả bbox/polygon, không enrich).

### 3. Fallback an toàn
- Nếu `best.pt` không load được, `DefectTypeService.model is None` → `extract` tự quay về
  heuristic cũ, không crash. Khớp với yêu cầu plan.

### 4. Sửa lỗi load checkpoint (`AI/defect_type/model_utils.py`)
- PyTorch >= 2.6 đổi mặc định `torch.load(weights_only=True)`, gây lỗi
  `UnpicklingError: Unsupported global: GLOBAL numpy._core.multiarray.scalar` khi load
  checkpoint cục bộ (chứa metadata numpy scalar).
- Sửa: `torch.load(checkpoint_path, map_location=device, weights_only=False)` (file đáng tin cậy).
- Sau sửa: test trên `test_image.jpg` → `Model loaded: True`, taxonomy `global`, 41 lớp,
  trả `defect_type=scratch` (conf 0.308) từ model thay vì heuristic.

### 5. Cập nhật tài liệu
- `backend/DEFECT_TYPE_INTEGRATION_CHECK.md`: đánh dấu ĐÃ TÍCH HỢP XONG, ghi chi tiết xác minh.

---

## Kiểm tra số lượng loại lỗi `label_map.json`
- File: `runs/classify/AI/defect-type/resnet18-global/label_map.json`
- **Thực tế: 41 lớp** (các key `"0"` → `"40"`).
- Plan `integrate_defect_type_model.md` ghi chú "taxonomy `global` ~15 loại lỗi" là
  **KHÔNG chính xác** so với label_map.json hiện tại (đếm được 41).
- LƯU Ý: `DefectTypeService` lấy `label_names` từ metadata của checkpoint (`payload["label_names"]`),
  không đọc `label_map.json`. Do đó số lớp thực tế khi chạy được quyết định bởi checkpoint,
  không phải file json này. Tuy nhiên `label_map.json` phản ánh taxonomy huấn luyện là 41 lớp.
- Các label là tên loại lỗi ngắn (scratch, crack, bent, ...) — khớp với expectation của
  report/VQA (không dạng `class__defect`).

---

## Kết quả mong đợi
- `/inspect` và `/process_video` trả `defect_type` từ model (vd `scratch`, `crack`) thay vì
  từ từ điển `PRODUCT_DEFECT_MAP`.
- Mỗi prediction enriched thêm `defect_type_confidence` và `defect_type_topk`.
- Nếu model null → fallback heuristic, không thay đổi hành vi cũ.

---

## Chưa thực hiện (theo plan)
- Chạy `python backend/_validate_defect_logic.py` để xác nhận heuristic cũ vẫn pass.
- Thêm script test gửi ảnh có defect và so sánh `defect_type_breakdown` trước/sau (cần ảnh mẫu thực tế).