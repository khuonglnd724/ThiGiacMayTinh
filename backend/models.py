import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, DateTime
from backend.database import Base

class InspectionLog(Base):
    __tablename__ = "inspection_logs"

    id = Column(Integer, primary_key=True, index=True)
    video_name = Column(String, index=True, nullable=True)
    frame_index = Column(Integer, nullable=True)
    timestamp = Column(Float, nullable=True)
    has_defect = Column(Boolean, default=False)
    predictions = Column(JSON, nullable=True)  # List of boxes/polygons
    saved_image_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
