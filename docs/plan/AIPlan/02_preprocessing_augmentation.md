Goal: Chuẩn hoá và tăng cường dữ liệu cho huấn luyện YOLO (segmentation)

Input:
- Dữ liệu thô trong `AI/dataset/mvtec-ad/` và manifest split

Output:
- Ảnh và mặt nạ đã resize, normalize và định dạng theo YOLO (labels + mask)
- Pipeline augmentation có thể tái dùng (script hoặc dataset class)

How to do:
1. Resize ảnh về kích thước làm việc: khuyến nghị 416×416 (hoặc 512×512 trên GPU lớn).
2. Chuẩn hoá pixel về [0,1] hoặc chuẩn ImageNet nếu dùng pretrained backbone.
3. Chuyển mask sang YOLO format (mask files + txt labels) hoặc COCO nếu cần.
4. Áp dụng augmentation nhẹ: horizontal/vertical flip, small rotation (±15°), brightness/contrast, gaussian noise, random crop/scale.
5. Tạo DataLoader với `num_workers=4` và `pin_memory=True` để CPU tiền xử lý cho GPU.

Lưu ý:
- Với VRAM 4GB, ưu tiên giảm kích thước ảnh và giới hạn augmentation thời gian huấn luyện.
- Lưu pipeline preprocessing dưới dạng script reproducible (scripts/preprocess.py).
