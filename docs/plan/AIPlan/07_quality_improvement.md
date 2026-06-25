Goal: Cải tiến chất lượng huấn luyện YOLO-seg cho bài toán phát hiện lỗi bề mặt

Input:
- Pipeline hiện tại: `AI/preprocess/preprocess.py`, `AI/train/train.py`, `AI/dataset/download_mvtec.py`
- Kết quả huấn luyện hiện tại: `runs/segment/AI/train/runs/ai-segmentation/segmentation/`
- Dataset MVTec AD đã chuẩn hoá và manifest split

Output:
- Bộ cấu hình cải tiến để train lại model với recall/mAP tốt hơn
- Danh sách thay đổi ưu tiên cho preprocessing, augmentation, image size, model size và lịch train
- Bộ tiêu chí kiểm tra để so sánh các lần train (10 / 50 / 100 epoch)

How to do:
1. Kiểm tra chất lượng dữ liệu trước khi train lại: số lượng ảnh defect theo từng split, số mask rỗng, ảnh/nhãn bị lệch, và các class/anomaly có quá ít mẫu hay không.
2. Giảm mất mát chi tiết: tránh resize cố định về 416 quá sớm trong preprocessing; giữ ảnh gốc hoặc giữ thêm phiên bản độ phân giải cao hơn để train/inference.
3. Tăng kích thước ảnh train nếu VRAM cho phép: thử `imgsz=640`, sau đó so sánh với 416 để xem defect nhỏ có được học tốt hơn không.
4. Tối ưu augmentation: giữ flip nhẹ, brightness/contrast vừa phải; giảm các phép xoay/crop quá mạnh vì có thể làm mất vết lỗi nhỏ hoặc méo mask.
5. Kiểm tra chất lượng nhãn mask: xác nhận mask khớp với ảnh sau resize/letterbox, loại bỏ sample có mask hỏng hoặc lệch biên.
6. Thực hiện ablation có kiểm soát: train cùng model với 10, 50 và 100 epoch, nhưng chỉ đánh giá kết luận sau khi dữ liệu và độ phân giải đã được cải thiện; dùng early stopping để tránh overfit.
7. So sánh model nhẹ và model mạnh hơn một bậc: bắt đầu với `yolo11n-seg`, sau đó thử biến thể lớn hơn nếu VRAM còn đủ và metrics chưa đạt.
8. Theo dõi metrics theo đúng mục tiêu: ưu tiên recall, mAP50(M), mAP50-95(M), FN rate, rồi mới đến precision; chọn checkpoint theo best validation, không chỉ theo epoch cuối.
9. Chốt cấu hình tốt nhất, cập nhật `train.py`/preprocess theo cấu hình đã kiểm chứng, rồi huấn luyện lại một lần chính thức để tạo `best.pt` mới.

Lưu ý:
- Tăng epoch lên 50 hoặc 100 chỉ hữu ích khi dữ liệu và độ phân giải đầu vào đã đủ tốt; nếu tín hiệu ảnh bị mất từ bước preprocess thì epoch cao chỉ làm model học lâu hơn trên dữ liệu kém.
- Với defect nhỏ, chất lượng ảnh gốc và cách giữ chi tiết quan trọng hơn việc train dài hơn.
- Nếu ảnh gốc đã đủ nét, ưu tiên sửa pipeline và nhãn trước khi nghĩ tới việc chụp lại ảnh.
- Mỗi lần train cần lưu lại `results.csv`, `args.yaml`, `best.pt`, và ghi log thay đổi để so sánh tái lập được.