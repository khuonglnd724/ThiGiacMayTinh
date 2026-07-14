import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO

try:
    from backend.config import get_yolo_path
except ImportError:
    from config import get_yolo_path

class YOLOService:
    def __init__(self):
        self.model_path = get_yolo_path()
        print(f"Đang tải mô hình YOLO-seg từ: {self.model_path}")
        self.model = YOLO(self.model_path)

    def predict(self, image: Image.Image | np.ndarray, conf: float = 0.25, task: str = "segment") -> tuple[list[dict], np.ndarray | None]:
        """
        Chạy suy luận trên ảnh và trả về kết quả dự đoán cùng ảnh đã chú thích (nếu có).
        
        task: "detect" hoặc "segment"
        """
        # Chuyển đổi PIL Image sang numpy array nếu cần
        if isinstance(image, Image.Image):
            img_np = np.array(image)
            # Chuyển RGB sang BGR cho Ultralytics/OpenCV
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = image

        results = self.model(img_bgr, conf=conf, verbose=False)
        predictions = []
        annotated_img = None

        if not results:
            return predictions, annotated_img

        result = results[0]
        # Lấy ảnh đã vẽ
        try:
            annotated_img = result.plot()  # Ảnh đã vẽ ở định dạng BGR
        except Exception as e:
            print(f"Lỗi khi render kết quả dự đoán lên ảnh: {e}")

        boxes = result.boxes
        masks = result.masks
        names = result.names

        if boxes is not None:
            for i in range(len(boxes)):
                box = boxes[i]
                xyxy = box.xyxy[0].tolist()  # [x_min, y_min, x_max, y_max]
                confidence = float(box.conf[0])
                cls = int(box.cls[0])
                class_name = names.get(cls, f"class_{cls}")

                pred = {
                    "class_id": cls,
                    "class_name": class_name,
                    "confidence": confidence,
                    "box": [round(val, 2) for val in xyxy]
                }

                # Nếu là tác vụ phân vùng và có mặt nạ
                if task == "segment" and masks is not None and len(masks.xyn) > i:
                    polygon = masks.xyn[i].tolist()  # Tọa độ đã chuẩn hóa [[x1, y1], [x2, y2], ...]
                    pred["polygon"] = [[round(p[0], 4), round(p[1], 4)] for p in polygon]

                predictions.append(pred)

        return predictions, annotated_img