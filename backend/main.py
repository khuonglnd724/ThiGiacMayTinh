import os
import shutil
import uuid
from contextlib import asynccontextmanager
import cv2
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.config import UPLOAD_DIR, STATIC_DIR, RESULTS_DIR
from backend.database import engine, get_db, Base
from backend.models import InspectionLog
from backend.services.yolo_service import YOLOService
from backend.services.caption_service import CaptionService
from backend.services.vqa_service import VQAService
from backend.services.feature_extraction import FeatureExtractor
from backend.services.inspection_report import InspectionReportService

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
async def vqa(file: UploadFile = File(...), question: str = Form(...)):
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = UPLOAD_DIR / temp_filename
    
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        img = Image.open(temp_path).convert("RGB")
        vqa_service: VQAService = app.state.vqa
        result_answer = vqa_service.answer_question(img, question)
        
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

@app.post("/process_video")
async def process_video(
    file: UploadFile = File(...),
    conf: float = 0.25,
    frame_skip: int = 5,
    db: Session = Depends(get_db)
):
    """
    Uploads a video, extracts frames at designated skip intervals, 
    runs YOLO segmentation, logs results to DB, and returns summary.
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
        
        yolo_service: YOLOService = app.state.yolo
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Skip frames to optimize performance
            if frame_idx % frame_skip == 0:
                inspected_count += 1
                timestamp_sec = round(frame_idx / fps, 2)
                
                # Predict on the frame (OpenCV returns BGR numpy array)
                predictions, annotated_bgr = yolo_service.predict(frame, conf=conf, task="segment")
                
                has_defect = any(pred["class_name"] == "defect" for pred in predictions)
                saved_image_path = None
                
                # If defect found, save the annotated frame
                if has_defect and annotated_bgr is not None:
                    defects_found += 1
                    saved_filename = f"video_{temp_filename}_frame_{frame_idx}.jpg"
                    saved_path = RESULTS_DIR / saved_filename
                    cv2.imwrite(str(saved_path), annotated_bgr)
                    saved_image_path = f"/static/results/{saved_filename}"
                
                # Save log record to DB
                log_entry = InspectionLog(
                    video_name=file.filename,
                    frame_index=frame_idx,
                    timestamp=timestamp_sec,
                    has_defect=has_defect,
                    predictions=predictions,
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
                    "predictions_count": len(predictions),
                    "saved_image_url": saved_image_path
                })
                
            frame_idx += 1
            
        cap.release()
        
        return {
            "status": "success",
            "video_name": file.filename,
            "total_frames_in_video": total_frames,
            "frames_inspected": inspected_count,
            "defects_found": defects_found,
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

