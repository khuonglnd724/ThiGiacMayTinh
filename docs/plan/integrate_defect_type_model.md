# Plan: Tích hợp mô hình phân loại defect-type (resnet18-global) vào backend

## Goal
Sử dụng mô hình đã huấn luyện `runs/classify/AI/defect-type/resnet18-global/weights/best.pt`
(classifier ResNet18, taxonomy `global` ~15 loại lỗi) để thay thế việc suy luận
`defect_type` bằng heuristic cứng hiện tại (`FeatureExtractor._classify_defect_type`),
giúp frontend nhận được loại lỗi chính xác hơn từ model thay vì từ từ điển cố định.

## Input
- Ảnh sản phẩm (`PIL.Image` RGB) từ request `/inspect` hoặc `/process_video`.
- Các prediction thô từ `YOLOService.predict(task="segment")`: mỗi prediction có
  `class_name`, `box` (4 giá trị chuẩn hóa 0-1) và/hoặc `polygon` (danh sách điểm).
- File checkpoint: `runs/classify/AI/defect-type/resnet18-global/weights/best.pt`
  (đã tồn tại, load được qua `backend/config.get_defect_type_path()`).

## Output
- Mỗi prediction được làm giàu thêm trường `defect_type` (từ label model, đã qua
  `_label_to_defect_type` → với taxonomy `global` trả đúng tên loại lỗi, ví dụ `scratch`),
  `defect_type_confidence` (độ tin cậy model) và `defect_type_topk` (top-3 dự đoán).
- Giữ nguyên luồng `InspectionReportService` / `VQAService` tiêu thụ `defect_type` như cũ.
- Nếu model không load được, fallback an toàn: giữ heuristic cũ (không crash).

## How to do
1. **Khởi tạo service trong `main.py`**
   - Thêm import: `from .services.defect_type_service import DefectTypeService`
     (và fallback `from services.defect_type_service import DefectTypeService`).
   - Trong `lifespan(app)`, sau khi tạo `yolo/caption/vqa`, thêm:
     `app.state.defect_type = DefectTypeService(device="cpu")`.
   - `DefectTypeService.__init__` đã tự load `best.pt` qua `get_defect_type_path()`;
     nếu file không tồn tại sẽ in "Failed to load" và `predict` trả `unknown` (an toàn).

2. **Gọi model trong `FeatureExtractor.extract`** (hoặc trong `/inspect` và `/process_video`)
   - `FeatureExtractor` cần tham chiếu đến service. Cách đơn giản: truyền service vào
     `extract(predictions, img_width, img_height, defect_type_service=None)`.
   - Với mỗi `pred` có `box` hoặc `polygon`:
     ```python
     if defect_type_service is not None and defect_type_service.model is not None:
         dt = defect_type_service.predict(img_pil, detection=pred, top_k=3)
         pred["defect_type"] = dt["defect_type"]
         pred["defect_type_confidence"] = dt["confidence"]
         pred["defect_type_topk"] = dt["top_k"]
     # else: giữ heuristic _classify_defect_type như hiện tại
     ```
   - `DefectTypeService.predict` tự cắt ROI từ `box`/`polygon` (padding 15%) rồi chạy
     `predict_pil` với `image_size` lấy từ metadata (224). Không cần resize thủ công.

3. **Nối luồng ở endpoint**
   - Trong `/inspect`: `enriched = extractor.extract(predictions, img_width, img_height,
     defect_type_service=app.state.defect_type)` (cần truyền `img` PIL gốc cho service).
   - Trong `/process_video`: tương tự, truyền `app.state.defect_type` và `frame` (chuyển
     BGR→RGB PIL) vào `extractor.extract`.
   - Trong `/segment` (chỉ trả bbox, không enrich) có thể bỏ qua hoặc cũng enrich tuỳ ý.

4. **Đảm bảo chạy đúng môi trường**
   - Backend phải chạy bằng `.venv` (đã có `torch` + package `AI` import được).
   - `DefectTypeService` import `from AI.defect_type.model_utils import ...`; nếu chạy
     backend từ thư mục gốc `d:\TGMT\ThiGiacMayTinh` thì import tuyệt đối `AI` hoạt động.

5. **Kiểm thử**
   - Chạy `python backend/_validate_defect_logic.py` (đã có) để xác nhận heuristic cũ.
   - Thêm script/endpoint test: gửi 1 ảnh có defect, kiểm tra `defect_type` trả về từ
     model (vd `scratch`, `crack`) thay vì từ từ điển (`cracked_insulation`, ...).
   - So sánh `defect_type_breakdown` trong report trước/sau.

## Lưu ý
- Model dùng taxonomy `global` → label là tên loại lỗi ngắn (scratch, crack, bent, ...),
  KHÔNG phải dạng `class__defect` như composite. `_label_to_defect_type` với taxonomy
  `global` trả thẳng `label`, nên khớp với `defect_type` expectation của report/VQA.
- Nếu sau này train lại bằng taxonomy `composite`, service vẫn chạy nhưng `_label_to_defect_type`
  sẽ tách `class__defect` → chỉ lấy phần defect; cần cập nhật mapping nếu muốn giữ class.
- Không xóa `FeatureExtractor._classify_defect_type`; giữ làm fallback khi model null.
- `get_defect_type_path()` luôn trả path dù file không tồn tại → service "Failed to load"
  là tình trạng an toàn, không block startup.
- File `best.pt` này là kết quả Run 2 (resnet18, global) — chưa bị ảnh hưởng bởi lỗi split
  của Run 1 (đã sửa trong `AI/defect_type/dataset.py`).