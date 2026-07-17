from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.database import init_db
from app.api.routes import router
from app.api.admin_routes import router as admin_router
from app.services.key_manager import key_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name}")
    await init_db()
    if settings.encryption_key:
        key_manager.init_encryption(settings.encryption_key, settings.openai_api_key)
        logger.info("Key manager initialized")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
        "http://localhost",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://frontend:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(admin_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
