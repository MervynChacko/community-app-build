from sqlalchemy import create_engine
# from sqlalchemy.ext.declarative import declarative_base   -- update due to pytest deprecation warning
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings


# Removed hardcoded database credentials and replaced with dynamic settings from app/core/config.py

# Construct engine using the dynamic DATABASE_URL from app/core/config.py
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency to get DB session in FastAPI endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
