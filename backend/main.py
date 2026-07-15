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
    from .services.defect_type_service import DefectTypeService
except ImportError:
    from config import UPLOAD_DIR, STATIC_DIR, RESULTS_DIR
    from database import engine, get_db, Base
    from models import InspectionLog
    from services.yolo_service import YOLOService
    from services.caption_service import CaptionService
    from services.vqa_service import VQAService
    from services.feature_extraction import FeatureExtractor
    from services.inspection_report import InspectionReportService
    from services.defect_type_service import DefectTypeService


def is_defect_frame(predictions):
    """Xác định frame có bị lỗi không dựa trên kết quả dự đoán từ mô hình."""
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
    """Xây dựng một loạt các frame kiểm tra băng chuyền mô phỏng."""
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
  <text x="120" y="110" fill="#f8fafc" font-family="Arial" font-size="18">Băng chuyền</text>
  <text x="340" y="110" fill="#f8fafc" font-family="Arial" font-size="18">Kiểm tra</text>
  {defect_markers}
  <rect x="420" y="220" width="120" height="24" rx="8" fill="#f59e0b" />
  <text x="80" y="300" fill="#f8fafc" font-family="Arial" font-size="24">Frame {frame_index} • {verdict} • {confidence:.2f} độ tin cậy</text>
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


# Quản lý vòng đời cho sự kiện khởi động/tắt máy chủ
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng trong CSDL
    Base.metadata.create_all(bind=engine)
    
    # Khởi tạo và lưu trữ dịch vụ AI trong app state
    print("Đang khởi tạo dịch vụ AI...")
    app.state.yolo = YOLOService()
    app.state.caption = CaptionService()
    app.state.vqa = VQAService()
    app.state.defect_type = DefectTypeService(device="cpu")
    print("Dịch vụ AI khởi tạo thành công.")
    yield
    # Dọn dẹp nếu cần
    print("Đang tắt máy chủ API...")

app = FastAPI(
    title="API Kiểm Tra Chất Lượng Bằng Thị Giác Máy Tính",
    description="API Backend cho phát hiện lỗi, phân vùng, chú thích ảnh và VQA.",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware CORS để kết nối với Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gắn thư mục static để phục vụ ảnh kết quả
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root():
    return {"message": "API Kiểm Tra Chất Lượng Bằng Thị Giác Máy Tính đang hoạt động"}

@app.get("/conveyor/simulate")
async def simulate_conveyor(frames: int = 8, interval_ms: int = 800, confidence: float = 0.25):
    """Trả về luồng mô phỏng các frame kiểm tra băng chuyền cho giao diện live."""
    so_frame_an_toan = max(1, min(int(frames), 12))
    khoang_cach_an_toan = max(200, int(interval_ms))
    do_tin_cay_an_toan = max(0.05, min(float(confidence), 0.99))

    return {
        "status": "success",
        "mode": "simulated_live",
        "interval_ms": khoang_cach_an_toan,
        "frames": build_simulated_conveyor_frames(
            frames=so_frame_an_toan,
            interval_ms=khoang_cach_an_toan,
            confidence=do_tin_cay_an_toan,
        ),
    }

@app.post("/detect")
async def detect(file: UploadFile = File(...), conf: float = 0.25):
    """Phát hiện đối tượng trong ảnh (chỉ bounding box, không phân vùng)."""
    # Lưu file tải lên
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = UPLOAD_DIR / temp_filename
    
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Đọc ảnh
        img = Image.open(temp_path).convert("RGB")
        
        # Chạy YOLO detection
        yolo_service: YOLOService = app.state.yolo
        predictions, annotated_bgr = yolo_service.predict(img, conf=conf, task="detect")
        
        result_url = None
        if annotated_bgr is not None:
            # Lưu ảnh đã chú thích
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
        raise HTTPException(status_code=500, detail=f"Lỗi chạy mô hình AI: {str(e)}")
    finally:
        # Xóa file tạm
        if temp_path.exists():
            os.remove(temp_path)

@app.post("/segment")
async def segment(file: UploadFile = File(...), conf: float = 0.25):
    """Phân vùng đối tượng trong ảnh (phát hiện + mặt nạ)."""
    # Lưu file tải lên
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = UPLOAD_DIR / temp_filename
    
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Đọc ảnh
        img = Image.open(temp_path).convert("RGB")
        
        # Chạy YOLO segmentation
        yolo_service: YOLOService = app.state.yolo
        predictions, annotated_bgr = yolo_service.predict(img, conf=conf, task="segment")
        
        result_url = None
        if annotated_bgr is not None:
            # Lưu ảnh đã chú thích
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
        raise HTTPException(status_code=500, detail=f"Lỗi chạy mô hình AI: {str(e)}")
    finally:
        # Xóa file tạm
        if temp_path.exists():
            os.remove(temp_path)

@app.post("/caption")
async def caption(file: UploadFile = File(...)):
    """Tạo chú thích cho ảnh."""
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
        raise HTTPException(status_code=500, detail=f"Lỗi tạo chú thích: {str(e)}")
    finally:
        if temp_path.exists():
            os.remove(temp_path)

@app.post("/vqa")
async def vqa(file: UploadFile = File(...), question: str = Form(...), context: Optional[str] = Form(None)):
    """Hỏi đáp trực quan về ảnh (Visual Question Answering)."""
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
        raise HTTPException(status_code=500, detail=f"Lỗi VQA: {str(e)}")
    finally:
        if temp_path.exists():
            os.remove(temp_path)

def detect_scene_change(frame1, frame2, threshold=5.0):
    """
    Phát hiện sự thay đổi cảnh giữa hai frame.
    Sử dụng HAI phương pháp để tăng độ chính xác:
    1. Sai số bình phương trung bình (MSE) - phát hiện thay đổi pixel rõ rệt
    2. So sánh biểu đồ màu (Chi-square) - cho ảnh cùng tông màu
    
    Trả về True nếu có cảnh/ảnh mới xuất hiện.
    Với video ghép từ nhiều ảnh, phương pháp này phát hiện khi ảnh mới xuất hiện.
    """
    if frame1 is None or frame2 is None:
        return True
    
    h, w = frame1.shape[:2]
    
    # Phương pháp 1: MSE (Sai số bình phương trung bình) - nhạy với thay đổi pixel
    diff_pixels = cv2.absdiff(frame1, frame2)
    mse = float((diff_pixels ** 2).sum()) / (h * w * 3)
    
    # Nếu MSE > 10, chắc chắn có thay đổi cảnh (2 ảnh khác nhau có MSE > 10-20)
    if mse > 10.0:
        return True
    
    # Phương pháp 2: So sánh biểu đồ Chi-square - cho ảnh cùng tông màu nhưng bố cục khác
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
    Tải lên video (gồm nhiều ảnh sản phẩm ghép lại), phát hiện thay đổi cảnh
    để chỉ xử lý các frame duy nhất, chạy YOLO segmentation, ghi log vào CSDL.
    
    Sử dụng phát hiện thay đổi cảnh để tránh xử lý các frame trùng lặp
    (cùng một ảnh xuất hiện nhiều lần trong video dạng trình chiếu).
    """
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    video_path = UPLOAD_DIR / temp_filename
    
    # Lưu video tải lên
    with video_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Không thể mở file video.")
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0  # Giá trị mặc định
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_idx = 0
        inspected_count = 0
        defects_found = 0
        logs = []
        max_frames_to_inspect = max(1, min(int(max_frames), 80))
        unique_images_found = 0
        last_processed_predictions = None
        last_processed_has_defect = False
        scene_first_frame = None  # Theo dõi frame đầu tiên của cảnh hiện tại
        
        yolo_service: YOLOService = app.state.yolo
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # --- PHÁT HIỆN THAY ĐỔI CẢNH ---
            # So sánh với Frame ĐẦU TIÊN của cảnh hiện tại (không phải frame trước đó)
            # Điều này xử lý chính xác các hiệu ứng chuyển cảnh mờ dần
            is_new_scene = (scene_first_frame is None) or detect_scene_change(scene_first_frame, frame, threshold=scene_threshold)
            
            if is_new_scene:
                # Đây là ảnh/frame duy nhất
                unique_images_found += 1
                
                if inspected_count >= max_frames_to_inspect:
                    break
                
                # Cập nhật frame đầu tiên của cảnh hiện tại
                scene_first_frame = frame.copy()
                
                inspected_count += 1
                timestamp_sec = round(frame_idx / fps, 2)
                
                # Dự đoán trên frame bằng YOLO (CHỈ 1 LẦN cho mỗi ảnh)
                predictions, annotated_bgr = yolo_service.predict(frame, conf=conf, task="segment")
                
                has_defect = is_defect_frame(predictions)
                saved_image_path = None
                
                # bổ sung thông tin dự đoán với FeatureExtraction + InspectionReport
                frame_height, frame_width = frame.shape[:2]
                enriched_predictions = predictions
                report = None
                if predictions:
                    try:
                        extractor = FeatureExtractor()
                        frame_rgb_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        enriched_predictions = extractor.extract(
                            predictions,
                            frame_width,
                            frame_height,
                            defect_type_service=app.state.defect_type,
                            img=frame_rgb_pil,
                        )
                        reporter = InspectionReportService()
                        report = reporter.generate_report(
                            enriched_predictions,
                            filename=file.filename,
                            image_size=(frame_width, frame_height)
                        )
                    except Exception as e:
                        print(f"Cảnh báo: Thất bại khi bổ sung thông tin ngữ cảnh cho frame {frame_idx}: {e}")
                        enriched_predictions = predictions
                
                # Lưu frame đã chú thích
                if annotated_bgr is not None:
                    saved_filename = f"video_{temp_filename}_scene_{unique_images_found}.jpg"
                    saved_path = RESULTS_DIR / saved_filename
                    cv2.imwrite(str(saved_path), annotated_bgr)
                    saved_image_path = f"/static/results/{saved_filename}"
                
                if has_defect:
                    defects_found += 1
                
                # Lưu vào CSDL (chỉ 1 bản ghi cho mỗi ảnh duy nhất)
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
                    "is_first_frame": True  # Đánh dấu: đây là frame đầu tiên của cảnh
                })
                
                last_processed_predictions = predictions
                last_processed_has_defect = has_defect
            
            # Bỏ qua các frame trùng lặp (không log, không YOLO)
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
        raise HTTPException(status_code=500, detail=f"Xử lý video thất bại: {str(e)}")
    finally:
        # Xóa file video tạm để tránh đầy bộ nhớ
        if video_path.exists():
            os.remove(video_path)

@app.get("/logs")
async def get_logs(limit: int = 100, skip: int = 0, db: Session = Depends(get_db)):
    """Lấy nhật ký kiểm tra từ cơ sở dữ liệu."""
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
async def inspect(file: UploadFile = File(...), conf: float = 0.25, db: Session = Depends(get_db)):
    """
    Quy trình kiểm tra đầy đủ:
      1. Phân vùng YOLO
      2. Trích xuất đặc trưng (loại lỗi, diện tích, vị trí, kích thước, mức độ)
      3. Báo cáo kiểm tra (kết luận & khuyến cáo dựa trên quy tắc)
      4. Tích hợp ngữ cảnh VQA
      5. Lưu kết quả vào database inspection_logs

    Luồng xử lý:
      Ảnh -> YOLO11-seg -> Phát hiện + Phân vùng
      -> Trích xuất đặc trưng -> Kiểm tra JSON
      -> Báo cáo kiểm tra + VQA Engine -> Phản hồi cuối cùng
      -> Lưu log vào database
    """
    # Lưu file tải lên
    file_ext = os.path.splitext(file.filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = UPLOAD_DIR / temp_filename

    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Đọc ảnh
        img = Image.open(temp_path).convert("RGB")
        img_width, img_height = img.size

        # Bước 1: Phân vùng YOLO
        yolo_service: YOLOService = app.state.yolo
        predictions, annotated_bgr = yolo_service.predict(img, conf=conf, task="segment")

        # Bước 2: Trích xuất đặc trưng (sử dụng mô hình defect-type nếu có)
        extractor = FeatureExtractor()
        enriched_predictions = extractor.extract(
            predictions,
            img_width,
            img_height,
            defect_type_service=app.state.defect_type,
            img=img,
        )

        # Lưu ảnh đã chú thích
        result_url = None
        if annotated_bgr is not None:
            result_filename = f"inspect_{temp_filename}"
            result_path = RESULTS_DIR / result_filename
            cv2.imwrite(str(result_path), annotated_bgr)
            result_url = f"/static/results/{result_filename}"

        # Bước 3: Báo cáo kiểm tra
        reporter = InspectionReportService()
        report = reporter.generate_report(
            enriched_predictions,
            filename=file.filename,
            image_size=(img_width, img_height)
        )

        # Bước 4: Ngữ cảnh VQA (câu trả lời sẵn cho các câu hỏi phổ biến)
        vqa_service: VQAService = app.state.vqa
        vqa_context = {
            "enriched_predictions": enriched_predictions,
            "report": report,
        }
        # Trả lời trước các câu hỏi phổ biến để truy cập nhanh
        common_questions = {
            "defect": vqa_service.answer_question(img, "Có lỗi gì không?", vqa_context),
            "severity": vqa_service.answer_question(img, "Mức độ nghiêm trọng thế nào?", vqa_context),
            "verdict": vqa_service.answer_question(img, "Kết luận là gì?", vqa_context),
            "position": vqa_service.answer_question(img, "Lỗi ở vị trí nào?", vqa_context),
            "count": vqa_service.answer_question(img, "Có bao nhiêu lỗi?", vqa_context),
        }

        # Bước 5: Lưu kết quả vào database
        has_defect = len(enriched_predictions) > 0
        log_entry = InspectionLog(
            video_name=file.filename,  # Dùng filename làm tên ảnh
            frame_index=0,
            timestamp=0.0,
            has_defect=has_defect,
            predictions=enriched_predictions,
            saved_image_path=result_url
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)

        # Phản hồi cuối cùng: dự đoán đã bổ sung thông tin + báo cáo + VQA + log_id
        return {
            "status": "success",
            "filename": file.filename,
            "image_size": f"{img_width}x{img_height}",
            "total_defects": len(enriched_predictions),
            "predictions": enriched_predictions,
            "result_image_url": result_url,
            "report": report,
            "vqa_quick_answers": common_questions,
            "log_id": log_entry.id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kiểm tra thất bại: {str(e)}")
    finally:
        # Xóa file tạm
        if temp_path.exists():
            os.remove(temp_path)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)