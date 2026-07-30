from fastapi import FastAPI
from app.database import Base, engine
import app.models  # Ensures models are registered with Base metadata
from app.routers import auth, posts  # Import the auth router

# Create database tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Apartment Community API",
    description="Backend API for apartment community messaging and marketplace.",
    version="1.0.0"
    )

# Include router modules
app.include_router(auth.router)
app.include_router(posts.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Villas @ Bellevue API"}
