# AI Services package for FastAPI Backend

try:
    from backend.services.yolo_service import YOLOService
    from backend.services.caption_service import CaptionService
    from backend.services.vqa_service import VQAService
    from backend.services.feature_extraction import FeatureExtractor
    from backend.services.inspection_report import InspectionReportService
except ImportError:
    from services.yolo_service import YOLOService
    from services.caption_service import CaptionService
    from services.vqa_service import VQAService
    from services.feature_extraction import FeatureExtractor
    from services.inspection_report import InspectionReportService

__all__ = [
    "YOLOService",
    "CaptionService",
    "VQAService",
    "FeatureExtractor",
    "InspectionReportService",
]

