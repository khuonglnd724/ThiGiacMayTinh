# Goal
Xây dựng model thứ 2 để xác định loại lỗi từ output của pipeline hiện tại.

Pipeline hiện tại đã làm tốt nhiệm vụ tìm vùng lỗi bằng YOLO segmentation. Plan này bổ sung một bước phân loại phía sau để dự đoán defect type chính xác hơn, thay vì suy luận từ polygon hay từ class sản phẩm.

# Input
1. **Output từ preprocessing hiện tại** trong `AI/preprocess/output/`:
   - `images/`: ảnh gốc hoặc ảnh đã chuẩn hóa cho từng split
   - `masks/`: mask nhị phân của vùng lỗi
   - `labels/`: polygon YOLO segmentation
   - `meta/`: metadata của pipeline
2. **Dữ liệu gốc MVTec AD** trong `AI/dataset/mvtec-ad/raw/` và `manifest/manifest.json`:
   - class sản phẩm
   - anomaly folder theo từng class
   - mask ground truth thật
3. **Kết quả từ model hiện tại**:
   - `class_name`
   - `box`
   - `polygon`
   - `confidence`
4. **Yêu cầu nghiệp vụ**:
   - cần phân biệt defect type ở mức thực dụng cho QC
   - chấp nhận output theo taxonomy riêng cho từng class nếu subtype giữa các class không đồng nhất

# Output
1. **Dataset cho model thứ 2**:
   - crop ROI theo mask/bbox
   - metadata train/val/test cho defect type
   - mapping nhãn defect type rõ ràng
2. **Model defect-type classifier**:
   - checkpoint train tốt nhất
   - checkpoint cuối cùng
   - metrics đánh giá
3. **Luồng suy luận mới**:
   - YOLO segmentation xác định vùng lỗi
   - model thứ 2 nhận crop ROI/mask crop và trả về defect type
   - backend trả kết quả có cả vị trí lẫn loại lỗi
4. **Tài liệu cấu hình**:
   - quy ước nhãn
   - cách tạo dataset
   - cách tích hợp vào backend

# How to do
## 1. Chốt lại bài toán phân loại
1. Không dùng polygon để đoán defect type cuối cùng.
2. Chọn một trong 2 chiến lược nhãn:
   - **Chiến lược A: per-class taxonomy**
     - mỗi class sản phẩm có tập defect type riêng
     - phù hợp nhất với MVTec AD
   - **Chiến lược B: taxonomy toàn cục**
     - gom defect type về nhóm chung như `scratch`, `crack`, `hole`, `contamination`, `deformation`
     - nhanh hơn nhưng ít chi tiết hơn
3. Khuyến nghị thực tế: bắt đầu bằng taxonomy toàn cục để ra kết quả nhanh, sau đó mở rộng sang per-class taxonomy nếu cần độ chính xác cao hơn.

## 2. Tạo dataset cho model thứ 2
1. Duyệt `manifest.json` và lấy sample có `label = defect`.
2. Với mỗi sample defect:
   - đọc ảnh gốc
   - đọc mask ground truth hoặc polygon output
   - lấy bounding box của mask hoặc polygon
   - crop ROI quanh vùng lỗi
   - thêm padding nhỏ để giữ ngữ cảnh xung quanh vùng lỗi
3. Lưu thêm metadata cho mỗi crop:
   - `class_name`
   - `anomaly_folder` hoặc `defect_type`
   - `source_image_path`
   - `mask_path`
   - `crop_box`
   - `split`
4. Nếu một ảnh có nhiều vùng lỗi, tạo nhiều ROI riêng, mỗi ROI là một sample.
5. Nếu cần phân loại cả ảnh không lỗi, thêm class `good` hoặc `normal` vào dataset. Nếu không cần, chỉ train trên defect samples.

## 3. Chọn kiểu model thứ 2
1. **Baseline nhanh nhất**:
   - classifier ảnh trên ROI crop
   - model nhỏ, dễ train, dễ deploy
2. **Nếu ROI rất nhỏ hoặc texture là tín hiệu chính**:
   - classifier mạnh hơn với backbone pretrained
   - ưu tiên kiến trúc nhẹ nhưng ổn định
3. **Nếu taxonomy khác nhau theo từng class sản phẩm**:
   - dùng 1 model chung có `class_name` làm metadata đầu vào
   - hoặc tách classifier theo từng nhóm class
4. Khuyến nghị triển khai ban đầu: 1 classifier chung cho toàn bộ defect ROI, sau đó nếu nhầm nhiều giữa các class thì chuyển sang per-class head.

## 4. Train model thứ 2
1. Chia train/val/test theo source sample để tránh leakage giữa crop từ cùng 1 ảnh.
2. Cân bằng số lượng sample giữa các defect type nếu có chênh lệch lớn.
3. Augment nhẹ cho ROI:
   - flip nhỏ
   - rotate nhỏ
   - color jitter vừa phải
   - không làm méo hình quá mạnh vì defect type có thể phụ thuộc texture
4. Theo dõi các metric:
   - accuracy
   - macro F1
   - confusion matrix
   - top-2 accuracy nếu nhãn gần nhau
5. Kiểm tra riêng các case dễ nhầm:
   - scratch vs crack
   - dent vs hole
   - contamination vs stain

## 5. Tích hợp với backend hiện tại
1. Giữ YOLO segmentation làm model định vị vùng lỗi.
2. Sau khi có `polygon` hoặc `box`, backend tạo crop ROI.
3. Gửi ROI vào model thứ 2 để lấy defect type.
4. Kết quả trả về nên gồm:
   - `class_name` của sản phẩm
   - `defect_type` từ model thứ 2
   - `confidence`
   - `area`
   - `position`
   - `severity`
5. Nếu confidence của model thứ 2 thấp, trả về defect type mức khái quát như `surface_anomaly` thay vì ép một subtype sai.

## 6. Kiểm thử và hiệu chỉnh
1. Test trên tập ảnh thật chưa thấy trong train.
2. So sánh:
   - defect type từ model cũ / heuristic hiện tại
   - defect type từ model thứ 2
3. Lưu các case sai vào log để cập nhật taxonomy hoặc bổ sung dữ liệu.
4. Nếu model thứ 2 học kém, ưu tiên kiểm tra lại chất lượng crop/mask và nhãn defect type trước khi đổi kiến trúc.

# Lưu ý
1. Output preprocessing hiện tại **chưa đủ** để train defect-type model nếu chỉ dùng nhãn class sản phẩm; phải tạo nhãn defect type từ anomaly folder hoặc manifest.
2. Không nên dùng polygon để quyết định subtype cuối cùng vì polygon chỉ mô tả hình học, không mô tả đầy đủ texture hay ngữ nghĩa lỗi.
3. Nếu mục tiêu là ra kết quả nhanh, ưu tiên taxonomy toàn cục trước, sau đó mới mở rộng sang phân loại chi tiết theo từng class.
4. Nếu một class sản phẩm chỉ có vài mẫu defect type, nên cân nhắc train riêng theo class hoặc gom nhãn về nhóm chung để tránh overfit.
5. Model thứ 2 chỉ nên quyết định defect type khi vùng lỗi đã được model thứ nhất xác định đủ ổn định.