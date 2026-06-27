from PIL import Image

class CaptionService:
    def __init__(self):
        self.pipeline = None
        self.enabled = False
        try:
            from transformers import pipeline
            print("Attempting to load Image Captioning model (Salesforce/blip-image-captioning-base)...")
            self.pipeline = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
            self.enabled = True
            print("Image Captioning model loaded successfully.")
        except Exception as e:
            print(f"Image captioning model loading skipped or failed (using fallback/mock): {e}")

    def generate_caption(self, image: Image.Image) -> str:
        if self.enabled and self.pipeline is not None:
            try:
                results = self.pipeline(image)
                if results and len(results) > 0:
                    return results[0].get("generated_text", "No caption generated.")
            except Exception as e:
                print(f"Error during captioning inference: {e}")
        
        # Fallback Mock Description
        return "An inspection image of an industrial component on a fixed surface under controlled studio lighting."
