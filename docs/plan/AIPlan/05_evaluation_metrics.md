Goal: Xác định quy trình đánh giá, metrics, và tiêu chí chấp nhận

Input:
- Checkpoints và `best.pt` từ quá trình huấn luyện
- Tập test đã được chuẩn hoá

Output:
- Báo cáo đánh giá: Precision, Recall, mAP, IoU, Dice, False Positive, False Negative
- File báo cáo (CSV/JSON) và plots/trend logs

How to do:
1. Viết `evaluate.py` để load checkpoint và chạy inference trên test set, tính các metrics.
2. Tính mAP theo IoU thresholds (0.5:0.95) cho detection; tính IoU và Dice cho segmentation mask.
3. Tạo báo cáo per-class, confusion matrix, và thống kê FN/FP với ngưỡng cảnh báo.
4. So sánh FN với yêu cầu dự án (target FN < 1–2%). Nếu không đạt, điều chỉnh threshold, augmentation, hoặc retrain.

Lưu ý:
- Với dataset nhỏ, hãy báo cáo confidence intervals cho metrics nếu cần.
- Lưu giữ seed và phiên bản code để đảm bảo reproducibility.
