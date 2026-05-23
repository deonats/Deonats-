import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import router
from db_session import engine
from models import Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="DEONATS KERNEL", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def root():
    return {"system": "DEONATS", "status": "KERNEL RUNNING"}
