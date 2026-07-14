from backend.services.feature_extraction import FeatureExtractor
from backend.services.inspection_report import InspectionReportService
from backend.main import is_defect_frame

extractor = FeatureExtractor()
reporter = InspectionReportService()

predictions = [
    {"class_name": "bottle", "confidence": 0.95, "box": [0.1, 0.1, 0.3, 0.3]},
    {"class_name": "scratch", "confidence": 0.88, "box": [0.4, 0.4, 0.5, 0.5], "polygon": [[0.4, 0.4], [0.5, 0.4], [0.5, 0.5], [0.4, 0.5]]},
]

enriched = extractor.extract(predictions, 1000, 1000)
report = reporter.generate_report(enriched, filename="sample.png", image_size=(1000, 1000))

defect_predictions = [p for p in enriched if not p.get("is_product", False)]

print("is_defect_frame_product_only=", is_defect_frame([predictions[0]]))
print("is_defect_frame_defect_only=", is_defect_frame([predictions[1]]))
print("defect_predictions_count=", len(defect_predictions))
print("report_total_defects=", report["inspection_summary"]["total_defects_found"])
print("report_defect_breakdown=", report["inspection_summary"]["defect_type_breakdown"])
