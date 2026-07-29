from fastapi import FastAPI
from app.database import Base, engine
import app.models  # Ensures models are registered with Base metadata
from app.routers import auth  # Import the auth router

# Create database tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Apartment Community API")

# Include router modules
app.include_router(auth.router)

@app.get("/")
def read_root():
    return {"message": "Apartment Community API is running!"}
