
---

## 1. Chuẩn bị Dữ liệu (Dataset Preparation)
* **Bộ dữ liệu sử dụng:** `mvtec-ad` ( "path = kagglehub.dataset_download("ipythonx/mvtec-ad")" và lưu path vào THIGIACMAYTINH\AI\dataset; Anomaly Detection Dataset), chuyên mô phỏng các sản phẩm công nghiệp có bề mặt cố định.
* **Mục tiêu xử lý dữ liệu:** Phục vụ bài toán phát hiện lỗi bề mặt (Defect Detection), phân vùng lỗi (Segmentation) và đánh giá chất lượng sản phẩm (QC).
* **Quy trình xử lý dữ liệu gốc:**
    * Phân loại thành hai nhóm chính: **Normal** (không lỗi) và **Anomaly** (có lỗi).
    * Gán nhãn các loại lỗi chi tiết: *Scratch (trầy xước), Crack (nứt), Dent (móp), Missing part (thiếu linh kiện)*.
    * Tạo mặt nạ phân vùng lỗi (Segmentation Mask).
* **Tỷ lệ phân chia dữ liệu (Data Split):**
    * **Train (Huấn luyện):** 70%
    * **Validation (Xác thực):** 20%
    * **Test (Kiểm thử):** 10%

## 2. Tiền xử lý & Tăng cường Dữ liệu (Data Preprocessing & Augmentation)
* **Tiền xử lý dữ liệu (Preprocessing):**
    * Thay đổi kích thước hình ảnh về kích thước chuẩn `640x640`.
    * Chuẩn hóa giá trị pixel về khoảng từ `0–1`.
    * Làm sạch dữ liệu, loại bỏ hoàn toàn các ảnh mờ, nhiễu hoặc ảnh lỗi kỹ thuật.
    * Định dạng lại Segmentation Mask theo chuẩn `YOLO format` hoặc `COCO format`.
* **Tăng cường dữ liệu (Augmentation):** Áp dụng các kỹ thuật biến đổi để tăng độ đa dạng cho tập dữ liệu, giúp mô hình hoạt động tốt trong môi trường nhà máy thực tế:
    * Lật ảnh (Horizontal / Vertical Flip), Xoay ảnh (Rotation).
    * Thay đổi ngẫu nhiên độ sáng/độ tương phản (Random Brightness / Contrast).
    * Thêm nhiễu Gauss (Gaussian Noise).
    * Cắt/Thu phóng ảnh ngẫu nhiên (Random Crop / Scale).

## 3. Quá trình Huấn luyện Mô hình (Model Training & Fine-tuning)
* **Kiến trúc mô hình:** Sử dụng **YOLO11-seg** (Mô hình phân vùng đã được huấn luyện sẵn - Pretrained Segmentation Model).
* **Mục tiêu huấn luyện:** Thực hiện đồng thời tác vụ nhận diện vật thể và phân vùng lỗi bề mặt.
* **Đầu ra mong đợi của bước huấn luyện (Output):** Bounding box (Khung bao lỗi), Segmentation mask (Vùng phủ lỗi) và Class label (Nhãn phân loại lỗi).
* **Cấu hình Huấn luyện (Hyperparameters):** Điều chỉnh các tham số chính gồm: *Epochs, Batch Size, Learning Rate* dựa trên thuật toán tối ưu **AdamW**.
* **Các chỉ số theo dõi trong quá trình Train:**
    * Training Loss & Validation Loss (Độ sai lệch).
    * mAP (Mean Average Precision - Độ chính xác trung bình).
    * IoU (Intersection over Union) & Dice Score (Độ tương đồng vùng phân vùng).

## 4. Đánh giá Mô hình & Kết quả Đầu ra (Evaluation & Model Output)
* **Đánh giá trên tập Test:** Sử dụng các tiêu chí đo lường nghiêm ngặt của hệ thống kiểm định chất lượng (QC) bao gồm: *Precision, Recall, mAP, IoU, Dice Score, False Positive (Báo lỗi sai)* và *False Negative (Bỏ sót lỗi)*.
* **Tiêu chuẩn dự án đặc biệt:** Tỷ lệ bỏ sót lỗi (**False Negative**) bắt buộc phải cực thấp (`< 1–2%`) để tránh đưa sản phẩm lỗi ra thị trường.
* **Kết quả đầu ra:** Xuất file trọng số tối ưu nhất mang tên **`best.pt`**. File này sẽ trực tiếp cấu hình cho hệ thống chạy thực tế (Inference Real-time), làm lõi xử lý cho Mô-đun 1 (Computer Vision) để nhận diện lỗi từ camera và đẩy dữ liệu lên Dashboard thống kê.

---

## 5. Pipeline Huấn luyện AI Tổng thể
```
[Tập dữ liệu gốc: MVTec AD]
          │
          ▼
   [Preprocessing] (Resize, Chuẩn hóa format Mask)
          │
          ▼
    [Augmentation] (Lật, Xoay, Thêm nhiễu, Đổi độ sáng)
          │
          ▼
[Train YOLO11-seg] (Fine-tuning với bộ tối ưu AdamW)
          │
          ▼
   [Evaluation] (Kiểm tra mAP, IoU, kiểm soát chặt FN/FP)
          │
          ▼
     [File: best.pt] ──> Tích hợp vào hệ thống chạy thực tế (Inference)
```