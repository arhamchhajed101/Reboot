from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.api.websocket import router as ws_router
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Optimal Trade Execution Backend & Deterministic Market Simulator API",
    lifespan=lifespan,
)

# Enable CORS for React frontend (Person 3)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API and WebSocket routes
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(ws_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Optimal Trade Execution Simulator Backend Active",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
    }
