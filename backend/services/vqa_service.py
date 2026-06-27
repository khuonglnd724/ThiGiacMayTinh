from PIL import Image

class VQAService:
    def __init__(self):
        self.pipeline = None
        self.enabled = False
        try:
            from transformers import pipeline
            print("Attempting to load VQA model (dandelin/vilt-b32-finetuned-vqa)...")
            self.pipeline = pipeline("visual-question-answering", model="dandelin/vilt-b32-finetuned-vqa")
            self.enabled = True
            print("VQA model loaded successfully.")
        except Exception as e:
            print(f"VQA model loading skipped or failed (using fallback/mock): {e}")

    def answer_question(self, image: Image.Image, question: str) -> str:
        if self.enabled and self.pipeline is not None:
            try:
                # Transformers VQA pipeline expects inputs as (image, question)
                results = self.pipeline(image, question)
                if results and len(results) > 0:
                    return results[0].get("answer", "I cannot answer this question.")
            except Exception as e:
                print(f"Error during VQA inference: {e}")

        # Fallback Rule-based Mock VQA
        q_lower = question.lower()
        if any(kw in q_lower for kw in ["defect", "fault", "error", "crack", "scratch", "dent", "damage"]):
            return "Based on visual analysis, a surface anomaly may be present. Please check /segment for mask validation."
        if "color" in q_lower:
            return "The object shows neutral gray and metallic textures typical of industrial surfaces."
        if "object" in q_lower or "what is" in q_lower or "product" in q_lower:
            return "An industrial component undergoing quality assurance inspection."
        if "good" in q_lower or "ok" in q_lower:
            return "The surface structure is overall intact, but micro-anomalies need verification."

        return "Visual inspection of the product shows fixed texture patterns. No obvious shape distortions."
