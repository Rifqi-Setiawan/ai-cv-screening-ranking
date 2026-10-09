"""Main FastAPI application entry point for CV Screening & Ranking Platform."""
from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import auth, cvs, health, jobs
from src.infrastructure.config import settings
from src.infrastructure.database import close_db_pool, get_db_pool
from src.infrastructure.logging import logger


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(f"Starting CV Screening Platform in {settings.APP_ENV} mode on port {settings.APP_PORT}...")
    await get_db_pool()
    yield
    logger.info("Shutting down CV Screening Platform...")
    await close_db_pool()


app = FastAPI(
    title="CV Screening & Ranking Platform API",
    version="1.0.0",
    description="High-precision rule-based & AI-assisted CV evaluation and ranking engine.",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(cvs.router)


@app.get("/")
async def root():
    return {
        "service": "CV Screening & Ranking Platform API",
        "status": "ONLINE",
        "version": "1.0.0",
        "documentation": "/docs",
    }
