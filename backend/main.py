from __future__ import annotations

import asyncio

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from analysis import analyze_frame, read_and_validate_csv  # noqa: E402
from cache import AnalysisCache  # noqa: E402
from llm import generate_insight  # noqa: E402
from schemas import (  # noqa: E402
    AnalysisResponse,
    HealthResponse,
    InsightRequest,
    InsightResponse,
)

app = FastAPI(
    title="SalesSight Lite API",
    version="1.0.0",
    description="Validated sales KPIs, a basic trend forecast, and optional Gemini explanations.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

cache = AnalysisCache()
insight_locks: dict[str, asyncio.Lock] = {}


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(file: UploadFile = File(...)) -> AnalysisResponse:
    frame = await read_and_validate_csv(file)
    response, summary = analyze_frame(frame, file.filename or "sales.csv")
    cache.put(response.analysis_id, summary)
    return response


@app.post("/insights", response_model=InsightResponse)
async def insights(request: InsightRequest) -> InsightResponse:
    entry = cache.get(request.analysis_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="This analysis expired or the server restarted. Upload the CSV again.",
        )
    if entry.insight is not None:
        return InsightResponse(analysis_id=request.analysis_id, insight=entry.insight, cached=True)

    lock = insight_locks.setdefault(request.analysis_id, asyncio.Lock())
    async with lock:
        entry = cache.get(request.analysis_id)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail="This analysis expired while waiting. Upload the CSV again.",
            )
        if entry.insight is not None:
            return InsightResponse(analysis_id=request.analysis_id, insight=entry.insight, cached=True)

        text = await generate_insight(entry.summary)
        if not cache.set_insight(request.analysis_id, text):
            raise HTTPException(
                status_code=404,
                detail="This analysis expired. Upload the CSV again.",
            )
        return InsightResponse(analysis_id=request.analysis_id, insight=text, cached=False)

