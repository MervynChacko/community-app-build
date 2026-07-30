from sqlalchemy import create_engine
# from sqlalchemy.ext.declarative import declarative_base   -- update due to pytest deprecation warning
from sqlalchemy.orm import sessionmaker, declarative_base

# database credentials
SQLALCHEMY_DATABASE_URL = (
    "postgresql://community_user:community_pass@localhost:5432/community_db"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency to get DB session in FastAPI endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
