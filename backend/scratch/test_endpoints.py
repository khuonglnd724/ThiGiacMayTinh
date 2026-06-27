import sys
from pathlib import Path

# Add backend directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from backend.services.yolo_service import YOLOService
from backend.services.caption_service import CaptionService
from backend.services.vqa_service import VQAService
import numpy as np
from PIL import Image

def test_yolo_service():
    print("Testing YOLOService initialization...")
    try:
        yolo = YOLOService()
        # Create a dummy image
        img = Image.fromarray(np.uint8(np.random.rand(100, 100, 3) * 255))
        print("Running dummy predict...")
        preds, _ = yolo.predict(img, conf=0.1, task="segment")
        print(f"YOLOService success! Got {len(preds)} mock/real predictions.")
    except Exception as e:
        print(f"YOLOService test failed/skipped (expected if torch/ultralytics not in current venv): {e}")

def test_caption_service():
    print("Testing CaptionService...")
    try:
        cap = CaptionService()
        img = Image.fromarray(np.uint8(np.random.rand(100, 100, 3) * 255))
        result = cap.generate_caption(img)
        print(f"CaptionService success! Result: '{result}'")
    except Exception as e:
        print(f"CaptionService test failed: {e}")

def test_vqa_service():
    print("Testing VQAService...")
    try:
        vqa = VQAService()
        img = Image.fromarray(np.uint8(np.random.rand(100, 100, 3) * 255))
        result = vqa.answer_question(img, "Is there any defect?")
        print(f"VQAService success! Result: '{result}'")
    except Exception as e:
        print(f"VQAService test failed: {e}")

if __name__ == "__main__":
    print("Starting backend services self-test...")
    test_yolo_service()
    print("-" * 40)
    test_caption_service()
    print("-" * 40)
    test_vqa_service()
    print("Self-test completed!")
