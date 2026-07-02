Goal: Thiết lập môi trường Python và phụ thuộc để huấn luyện reproducible

Input:
- Thư mục dự án, quyền cài đặt Python/pip, (tuỳ chọn) CUDA driver tương thích

Output:
- `requirements.txt` hoặc `environment.yml` với các phiên bản khuyến nghị
- Hướng dẫn cài đặt ngắn (README) và lệnh thử nghiệm smoke

How to do:
1. Chuẩn hoá Python version: khuyến nghị Python 3.10+.
2. Tạo `requirements.txt` gồm: torch (phiên bản phù hợp với CUDA), torchvision, ultralytics (hoặc yolov11-seg), albumentations, opencv-python, tqdm, tensorboard, wandb (tuỳ chọn).
3. Hướng dẫn cài CUDA/PyTorch: cung cấp lệnh `pip`/`conda` cụ thể theo GPU và driver.
4. Tạo virtualenv và cài dependencies, kiểm tra bằng `python -c "import torch; print(torch.cuda.is_available())"`.
5. Ghi rõ biến môi trường cần thiết (e.g., WANDB_API_KEY nếu dùng W&B).

Lưu ý:
- Nếu không có GPU, cài torch CPU-only, nhưng training sẽ rất chậm.
- Với GTX1650 (CUDA 11.x), chọn PyTorch + CUDA tương thích.
