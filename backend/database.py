from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

try:
    from backend.config import DATABASE_URL
except ImportError:
    from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Hàm hỗ trợ tiêm phụ thuộc để tạo phiên CSDL."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
