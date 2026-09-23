"""Notification Translator - FastAPI application entrypoint."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models.notification import AnalyzeRequest, AnalyzeResponse, HealthResponse
from app.services.analyzer import analyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR.parent / "static"

app = FastAPI(title="Notification Translator", version="1.0.0")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    notifications = [n for n in (payload.notifications or []) if n and n.strip()]

    if not notifications:
        raise HTTPException(
            status_code=400,
            detail="Please provide at least one non-empty notification.",
        )

    if len(notifications) > 100:
        raise HTTPException(
            status_code=400,
            detail="Too many notifications at once (limit is 100).",
        )

    try:
        results = analyzer.analyze_many(notifications)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error during analysis")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while analyzing notifications. Please try again.",
        )

    return AnalyzeResponse(total=len(results), results=results)
