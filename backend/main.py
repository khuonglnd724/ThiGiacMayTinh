import base64
import os
import shutil
import uuid
import json
from typing import Optional
from contextlib import asynccontextmanager
import cv2
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import uvicorn

try:
    from .config import UPLOAD_DIR, STATIC_DIR, RESULTS_DIR
    from .database import engine, get_db, Base
    from .models import InspectionLog
    from .services.yolo_service import YOLOService
    from .services.caption_service import CaptionService
    from .services.vqa_service import VQAService
    from .services.feature_extraction import FeatureExtractor
    from .services.inspection_report import InspectionReportService
except ImportError:
    from config import UPLOAD_DIR, STATIC_DIR, RESULTS_DIR
    from database import engine, get_db, Base
    from models import InspectionLog
    from services.yolo_service import YOLOService
    from services.caption_service import CaptionService
    from services.vqa_service import VQAService
    from services.feature_extraction import FeatureExtractor
    from services.inspection_report import InspectionReportService

def is_defect_frame(predictions):
    """Treat a frame as defective when the model returns any meaningful defect-like prediction."""
    if not predictions:
        return False

    defect_keywords = {
        "defect",
        "scratch",
        "dent",
        "crack",
        "break",
        "chip",
        "spot",
        "bubble",
        "deform",
        "contamination",
    }

    for pred in predictions:
        class_name = str(pred.get("class_name", "")).lower()
        confidence = float(pred.get("confidence", 0) or 0)
        if any(keyword in class_name for keyword in defect_keywords) or confidence >= 0.7:
            return True

    return False


def build_simulated_conveyor_frames(frames=8, interval_ms=800, confidence=0.25):
    """Build a deterministic batch of synthetic conveyor inspection frames."""
    generated_frames = []

    for frame_index in range(1, frames + 1):
        defect_count = 1 if frame_index % 3 == 0 else 0
        if frame_index % 5 == 0:
            defect_count = 2

        verdict = "REJECT" if defect_count >= 2 else "FLAG" if defect_count > 0 else "PASS"
        defect_color = "#ff4d4f" if verdict != "PASS" else "#4caf50"

        defect_markers = ""
        for offset in range(defect_count):
            x = 120 + offset * 70 + (frame_index * 8 % 40)
            y = 90 + offset * 40 + (frame_index % 3) * 18
            defect_markers += (
                f'<rect x="{x}" y="{y}" width="46" height="30" rx="8" '
                f'fill="{defect_color}" stroke="#ffffff" stroke-width="3" />'
            )

        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">
  <rect width="640" height="360" fill="#0f172a" />
  <rect x="40" y="70" width="560" height="220" rx="30" fill="#111827" stroke="#38bdf8" stroke-width="4" />
  <rect x="60" y="210" width="520" height="40" rx="20" fill="#1f2937" />
  <rect x="80" y="180" width="480" height="20" rx="10" fill="#475569" />
  <circle cx="130" cy="125" r="16" fill="#fbbf24" />
  <circle cx="510" cy="125" r="16" fill="#34d399" />
  <rect x="80" y="90" width="180" height="30" rx="12" fill="#334155" />
  <rect x="300" y="90" width="180" height="30" rx="12" fill="#334155" />
  <text x="120" y="110" fill="#f8fafc" font-family="Arial" font-size="18">Conveyor</text>
  <text x="340" y="110" fill="#f8fafc" font-family="Arial" font-size="18">Inspection</text>
  {defect_markers}
  <rect x="420" y="220" width="120" height="24" rx="8" fill="#f59e0b" />
  <text x="80" y="300" fill="#f8fafc" font-family="Arial" font-size="24">Frame {frame_index} • {verdict} • {confidence:.2f} confidence</text>
</svg>'''

        encoded_svg = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        generated_frames.append(
            {
                "frame_index": frame_index,
                "timestamp": round(frame_index * interval_ms / 1000, 2),
                "verdict": verdict,
                "defect_count": defect_count,
                "confidence": confidence,
                "image_url": f"data:image/svg+xml;base64,{encoded_svg}",
            }
        )

    return generated_frames


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    Base.metadata.create_all(bind=engine)
    
    # Initialize and cache AI services in app state
    print("Initializing AI services...")
    app.state.yolo = YOLOService()
    app.state.caption = CaptionService()
    app.state.vqa = VQAService()
    print("AI services initialized successfully.")
    yield
    # Cleanup if needed
    print("Shutting down API server...")

app = FastAPI(
    title="Computer Vision Quality Control API",
    description="Backend API for defect detection, segmentation, image captioning, and VQA.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware to connect with Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder to serve result images
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root():
    return {"message": "Computer Vision Quality Control API is active"}

@app.get("/conveyor/simulate")
async def simulate_conveyor(frames: int = 8, interval_ms: int = 800, confidence: float = 0.25):
    """Return a simulated stream of conveyor inspection frames for the live UI."""
    safe_frame_count = max(1, min(int(frames), 12))
    safe_interval = max(200, int(interval_ms))
    safe_confidence = max(0.05, min(float(confidence), 0.99))

    return {
        "status": "success",
        "mode": "simulated_live",
        "interval_ms": safe_interval,
        "frames": build_simulated_conveyor_frames(
            frames=safe_frame_count,
            interval_ms=safe_interval,
            confidence=safe_confidence,
        ),
    }

@app.post("/detect")
async def detect(file: UploadFile = File(...), conf: float = 0.25):
    # Save uploaded file
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = UPLOAD_DIR / temp_filename
    
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Load image
        img = Image.open(temp_path).convert("RGB")
        
        # Run YOLO detection
        yolo_service: YOLOService = app.state.yolo
        predictions, annotated_bgr = yolo_service.predict(img, conf=conf, task="detect")
        
        result_url = None
        if annotated_bgr is not None:
            # Save annotated image
            result_filename = f"detect_{temp_filename}"
            result_path = RESULTS_DIR / result_filename
            cv2.imwrite(str(result_path), annotated_bgr)
            result_url = f"/static/results/{result_filename}"
            
        return {
            "status": "success",
            "filename": file.filename,
            "predictions": predictions,
            "result_image_url": result_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
    finally:
        # Cleanup temp file
        if temp_path.exists():
            os.remove(temp_path)

@app.post("/segment")
async def segment(file: UploadFile = File(...), conf: float = 0.25):
    # Save uploaded file
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = UPLOAD_DIR / temp_filename
    
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Load image
        img = Image.open(temp_path).convert("RGB")
        
        # Run YOLO segmentation
        yolo_service: YOLOService = app.state.yolo
        predictions, annotated_bgr = yolo_service.predict(img, conf=conf, task="segment")
        
        result_url = None
        if annotated_bgr is not None:
            # Save annotated image
            result_filename = f"segment_{temp_filename}"
            result_path = RESULTS_DIR / result_filename
            cv2.imwrite(str(result_path), annotated_bgr)
            result_url = f"/static/results/{result_filename}"
            
        return {
            "status": "success",
            "filename": file.filename,
            "predictions": predictions,
            "result_image_url": result_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
    finally:
        # Cleanup temp file
        if temp_path.exists():
            os.remove(temp_path)

@app.post("/caption")
async def caption(file: UploadFile = File(...)):
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = UPLOAD_DIR / temp_filename
    
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        img = Image.open(temp_path).convert("RGB")
        caption_service: CaptionService = app.state.caption
        result_caption = caption_service.generate_caption(img)
        
        return {
            "status": "success",
            "filename": file.filename,
            "caption": result_caption
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Caption generation error: {str(e)}")
    finally:
        if temp_path.exists():
            os.remove(temp_path)

@app.post("/vqa")
async def vqa(file: UploadFile = File(...), question: str = Form(...), context: Optional[str] = Form(None)):
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = UPLOAD_DIR / temp_filename
    
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        img = Image.open(temp_path).convert("RGB")
        vqa_service: VQAService = app.state.vqa
        
        inspection_context = None
        if context:
            try:
                inspection_context = json.loads(context)
            except Exception:
                pass
                
        result_answer = vqa_service.answer_question(img, question, inspection_context=inspection_context)
        
        return {
            "status": "success",
            "filename": file.filename,
            "question": question,
            "answer": result_answer
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VQA error: {str(e)}")
    finally:
        if temp_path.exists():
            os.remove(temp_path)

def detect_scene_change(frame1, frame2, threshold=5.0):
    """
    Detect if there is a significant scene change between two frames.
    Uses TWO methods for robustness:
    1. Mean Squared Error (pixel difference) - phát hiện thay đổi pixel rõ rệt
    2. Histogram comparison (Chi-square) - cho ảnh cùng tông màu
    
    Returns True if a new scene/image appears.
    For video composed of stitched images, this detects when a new image appears.
    """
    if frame1 is None or frame2 is None:
        return True
    
    h, w = frame1.shape[:2]
    
    # Method 1: MSE (Mean Squared Error) - nhạy với thay đổi pixel
    diff_pixels = cv2.absdiff(frame1, frame2)
    mse = float((diff_pixels ** 2).sum()) / (h * w * 3)
    
    # If MSE > 10, definitely a scene change (2 ảnh khác nhau có MSE > 10-20)
    if mse > 10.0:
        return True
    
    # Method 2: Histogram Chi-square - cho ảnh cùng tông màu nhưng bố cục khác
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    hist1 = cv2.calcHist([gray1], [0], None, [256], [0, 256])
    hist2 = cv2.calcHist([gray2], [0], None, [256], [0, 256])
    
    cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
    cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)
    
    hist_diff = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CHISQR)
    
    return hist_diff > threshold


@app.post("/process_video")
async def process_video(
    file: UploadFile = File(...),
    conf: float = 0.25,
    max_frames: int = Form(40),
    scene_threshold: float = Form(30.0),
    db: Session = Depends(get_db)
):
    """
    Uploads a video (composed of stitched product images), detects scene changes 
    to process only unique frames, runs YOLO segmentation, logs results to DB.
    
    Uses scene change detection to avoid processing duplicate frames 
    (same image appearing multiple times in a slideshow video).
    """
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    video_path = UPLOAD_DIR / temp_filename
    
    # Save uploaded video
    with video_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Cannot open video file.")
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0  # Fallback
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_idx = 0
        inspected_count = 0
        defects_found = 0
        logs = []
        max_frames_to_inspect = max(1, min(int(max_frames), 80))
        unique_images_found = 0
        last_processed_predictions = None
        last_processed_has_defect = False
        scene_first_frame = None  # Track first frame of current scene
        
        yolo_service: YOLOService = app.state.yolo
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # --- SCENE CHANGE DETECTION ---
            # Compare with FIRST frame of current scene (not previous frame)
            # This handles fade transitions correctly
            is_new_scene = (scene_first_frame is None) or detect_scene_change(scene_first_frame, frame, threshold=scene_threshold)
            
            if is_new_scene:
                # This is a unique image/frame
                unique_images_found += 1
                
                if inspected_count >= max_frames_to_inspect:
                    break
                
                # Update first frame of current scene
                scene_first_frame = frame.copy()
                
                inspected_count += 1
                timestamp_sec = round(frame_idx / fps, 2)
                
                # Predict on the frame using YOLO (CHỈ 1 LẦN cho mỗi ảnh)
                predictions, annotated_bgr = yolo_service.predict(frame, conf=conf, task="segment")
                
                has_defect = is_defect_frame(predictions)
                saved_image_path = None
                
                # Enrich predictions with FeatureExtraction + InspectionReport
                frame_height, frame_width = frame.shape[:2]
                enriched_predictions = predictions
                report = None
                if predictions:
                    try:
                        extractor = FeatureExtractor()
                        enriched_predictions = extractor.extract(predictions, frame_width, frame_height)
                        reporter = InspectionReportService()
                        report = reporter.generate_report(
                            enriched_predictions,
                            filename=file.filename,
                            image_size=(frame_width, frame_height)
                        )
                    except Exception as e:
                        print(f"Warning: Enrich failed for frame {frame_idx}: {e}")
                        enriched_predictions = predictions
                
                # Save annotated frame
                if annotated_bgr is not None:
                    saved_filename = f"video_{temp_filename}_scene_{unique_images_found}.jpg"
                    saved_path = RESULTS_DIR / saved_filename
                    cv2.imwrite(str(saved_path), annotated_bgr)
                    saved_image_path = f"/static/results/{saved_filename}"
                
                if has_defect:
                    defects_found += 1
                
                # Save to DB (only 1 record per unique image)
                log_entry = InspectionLog(
                    video_name=file.filename,
                    frame_index=frame_idx,
                    timestamp=timestamp_sec,
                    has_defect=has_defect,
                    predictions=enriched_predictions,
                    saved_image_path=saved_image_path
                )
                db.add(log_entry)
                db.commit()
                db.refresh(log_entry)
                
                logs.append({
                    "id": log_entry.id,
                    "frame_index": frame_idx,
                    "timestamp": timestamp_sec,
                    "has_defect": has_defect,
                    "predictions_count": len(enriched_predictions),
                    "predictions": enriched_predictions,
                    "report": report,
                    "saved_image_url": saved_image_path,
                    "is_first_frame": True  # Flag: this is the first frame of the scene
                })
                
                last_processed_predictions = predictions
                last_processed_has_defect = has_defect
            
            # Skip duplicate frames entirely (no log, no YOLO)
            frame_idx += 1
            
        cap.release()
        
        return {
            "status": "success",
            "video_name": file.filename,
            "total_frames_in_video": total_frames,
            "unique_images_detected": unique_images_found,
            "frames_inspected": inspected_count,
            "defects_found": defects_found,
            "max_frames_limit": max_frames_to_inspect,
            "scene_threshold": scene_threshold,
            "logs": logs
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video processing failed: {str(e)}")
    finally:
        # Cleanup temp video file to avoid storage bloat
        if video_path.exists():
            os.remove(video_path)

@app.get("/logs")
async def get_logs(limit: int = 100, skip: int = 0, db: Session = Depends(get_db)):
    """Retrieves previous inspection logs from database."""
    logs = db.query(InspectionLog).order_by(InspectionLog.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "status": "success",
        "count": len(logs),
        "logs": [
            {
                "id": log.id,
                "video_name": log.video_name,
                "frame_index": log.frame_index,
                "timestamp": log.timestamp,
                "has_defect": log.has_defect,
                "predictions": log.predictions,
                "saved_image_url": log.saved_image_path,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]
    }

@app.post("/inspect")
async def inspect(file: UploadFile = File(...), conf: float = 0.25):
    """
    Full inspection pipeline:
      1. YOLO segmentation
      2. Feature Extraction (defect type, area, position, size, severity)
      3. Inspection Report (rule-based verdict & recommendations)
      4. VQA context integration

    Follows the flow:
      Image -> YOLO11-seg -> Detection+Segmentation
      -> Feature Extraction -> JSON Inspection
      -> Inspection Report + VQA Engine -> Final Response
    """
    # Save uploaded file
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = UPLOAD_DIR / temp_filename

    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Load image
        img = Image.open(temp_path).convert("RGB")
        img_width, img_height = img.size

        # Step 1: YOLO segmentation
        yolo_service: YOLOService = app.state.yolo
        predictions, annotated_bgr = yolo_service.predict(img, conf=conf, task="segment")

        # Step 2: Feature Extraction
        extractor = FeatureExtractor()
        enriched_predictions = extractor.extract(predictions, img_width, img_height)

        # Save annotated image
        result_url = None
        if annotated_bgr is not None:
            result_filename = f"inspect_{temp_filename}"
            result_path = RESULTS_DIR / result_filename
            cv2.imwrite(str(result_path), annotated_bgr)
            result_url = f"/static/results/{result_filename}"

        # Step 3: Inspection Report
        reporter = InspectionReportService()
        report = reporter.generate_report(
            enriched_predictions,
            filename=file.filename,
            image_size=(img_width, img_height)
        )

        # Step 4: VQA context (pre-built answers for common questions)
        vqa_service: VQAService = app.state.vqa
        vqa_context = {
            "enriched_predictions": enriched_predictions,
            "report": report,
        }
        # Pre-answer common questions for quick access
        common_questions = {
            "defect": vqa_service.answer_question(img, "Is there any defect?", vqa_context),
            "severity": vqa_service.answer_question(img, "What is the severity?", vqa_context),
            "verdict": vqa_service.answer_question(img, "What is the verdict?", vqa_context),
            "position": vqa_service.answer_question(img, "Where is the defect?", vqa_context),
            "count": vqa_service.answer_question(img, "How many defects?", vqa_context),
        }

        # Final Response: enriched predictions + report + VQA
        return {
            "status": "success",
            "filename": file.filename,
            "image_size": f"{img_width}x{img_height}",
            "total_defects": len(enriched_predictions),
            "predictions": enriched_predictions,
            "result_image_url": result_url,
            "report": report,
            "vqa_quick_answers": common_questions,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inspection failed: {str(e)}")
    finally:
        # Cleanup temp file
        if temp_path.exists():
            os.remove(temp_path)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

