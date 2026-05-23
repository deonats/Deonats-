from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db.session import engine
from app.models.models import Base

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DEONATS KERNEL",
    description="Financial OS — Industrial Brutalism",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "system": "DEONATS",
        "version": "1.0.0",
        "status": "KERNEL RUNNING",
        "docs": "/docs",
    }
