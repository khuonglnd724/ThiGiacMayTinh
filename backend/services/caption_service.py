from PIL import Image

class CaptionService:
    def __init__(self):
        self.pipeline = None
        self.enabled = False
        try:
            from transformers import pipeline
            print("Đang tải mô hình chú thích ảnh (Salesforce/blip-image-captioning-base)...")
            self.pipeline = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
            self.enabled = True
            print("Mô hình chú thích ảnh đã tải thành công.")
        except Exception as e:
            print(f"Tải mô hình chú thích ảnh thất bại hoặc bị bỏ qua (dùng dự phòng/mock): {e}")

    def generate_caption(self, image: Image.Image) -> str:
        if self.enabled and self.pipeline is not None:
            try:
                results = self.pipeline(image)
                if results and len(results) > 0:
                    return results[0].get("generated_text", "Không có chú thích nào được tạo.")
            except Exception as e:
                print(f"Lỗi trong quá trình suy luận chú thích: {e}")
        
        # Mô tả dự phòng (Mock)
        return "Ảnh kiểm tra của một linh kiện công nghiệp trên bề mặt cố định dưới ánh sáng studio có kiểm soát."