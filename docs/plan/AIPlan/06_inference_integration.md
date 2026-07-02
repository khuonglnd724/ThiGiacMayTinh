Goal: Tích hợp trọng số `best.pt` vào hệ thống inference real-time và dashboard

Input:
- File `best.pt` (sau khi huấn luyện)
- Pipeline thu hình từ camera và phần backend dashboard

Output:
- Script inference (inference.py) cho real-time: nhận khung ảnh, trả bounding boxes, segmentation masks, class label
- Hướng dẫn tối ưu hoá latency (FP16, ONNX, TensorRT nếu có GPU hỗ trợ)

How to do:
1. Viết `inference.py` dùng phiên bản model nhẹ, tải `best.pt`, chuẩn hoá ảnh tương tự pipeline huấn luyện.
2. Nếu GPU yếu, bật FP16 và giảm input resolution để giảm latency.
3. Cân nhắc xuất sang ONNX và chạy inference qua ONNXRuntime hoặc TensorRT cho throughput thấp-latency.
4. Kết nối output tới module Dashboard (REST API hoặc message queue) để lưu kết quả và thống kê.

Lưu ý:
- Thử nghiệm latency trên thiết bị mục tiêu và điều chỉnh kích thước ảnh / batch size.
- Kiểm soát false alarms (FP) bằng thresholding và hậu xử lý (morphology trên mask).
Goal: Tích hợp trọng số `best.pt` vào hệ thống inference real-time và dashboard

Input:
- File `best.pt` (sau khi huấn luyện)
- Pipeline thu hình từ camera và phần backend dashboard

Output:
- Script inference (inference.py) cho real-time: nhận khung ảnh, trả bounding boxes, segmentation masks, class label
- Hướng dẫn tối ưu hoá latency (FP16, ONNX, TensorRT nếu có GPU hỗ trợ)

How to do:
1. Viết `inference.py` dùng phiên bản model nhẹ, tải `best.pt`, chuẩn hoá ảnh tương tự pipeline huấn luyện.
2. Nếu GPU yếu, bật FP16 và giảm input resolution để giảm latency.
3. Cân nhắc xuất sang ONNX và chạy inference qua ONNXRuntime hoặc TensorRT cho throughput thấp-latency.
4. Kết nối output tới module Dashboard (REST API hoặc message queue) để lưu kết quả và thống kê.

Lưu ý:
- Thử nghiệm latency trên thiết bị mục tiêu và điều chỉnh kích thước ảnh / batch size.
- Kiểm soát false alarms (FP) bằng thresholding và hậu xử lý (morphology trên mask).
