import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO
from backend.config import get_yolo_path

class YOLOService:
    def __init__(self):
        self.model_path = get_yolo_path()
        print(f"Loading YOLO-seg model from: {self.model_path}")
        self.model = YOLO(self.model_path)

    def predict(self, image: Image.Image | np.ndarray, conf: float = 0.25, task: str = "segment") -> tuple[list[dict], np.ndarray | None]:
        """
        Runs inference on the image and returns predictions and optionally the annotated image.
        
        task: "detect" or "segment"
        """
        # Convert PIL Image to numpy array if needed
        if isinstance(image, Image.Image):
            img_np = np.array(image)
            # Convert RGB to BGR for Ultralytics/OpenCV
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = image

        results = self.model(img_bgr, conf=conf, verbose=False)
        predictions = []
        annotated_img = None

        if not results:
            return predictions, annotated_img

        result = results[0]
        # Get plotted image
        try:
            annotated_img = result.plot()  # Plotted image in BGR format
        except Exception as e:
            print(f"Error plotting predictions: {e}")

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

                # If it's a segmentation task and masks exist
                if task == "segment" and masks is not None and len(masks.xyn) > i:
                    polygon = masks.xyn[i].tolist()  # Normalized coordinates [[x1, y1], [x2, y2], ...]
                    pred["polygon"] = [[round(p[0], 4), round(p[1], 4)] for p in polygon]

                predictions.append(pred)

        return predictions, annotated_img
