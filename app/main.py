from fastapi import FastAPI

import app.models  # Ensures models are registered with Base metadata
from app.routers import auth, posts , staff, channels

"""
# Create database tables automatically
# REMOVED: 
# from app.database import Base, engine
# Base.metadata.create_all(bind=engine)

# This was firing on every app import -- including every container
# restart and every pytest run (tests/test_posts.py imports `app` from
# this module) -- and racing against Alembic. It silently created
# schema (tables, and Postgres ENUM types with the wrong label casing)
# before migrations ever ran, which is what caused both the earlier
# DuplicateColumn/orphaned-channels-table issues and this migration's
# "invalid input value for enum userrole" error.
"""

app = FastAPI(
    title="Apartment Community API",
    description="Backend API for apartment community messaging and marketplace.",
    version="1.0.0"
    )

# Include router modules
app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(staff.router)
app.include_router(channels.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Villas @ Bellevue API"}
