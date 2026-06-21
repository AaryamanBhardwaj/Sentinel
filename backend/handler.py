"""Lambda entry point — FastAPI app served via Mangum for API Gateway.

Local dev:  uvicorn backend.handler:app --reload --port 8000
Lambda:     the `handler` variable is the Mangum-wrapped entry point.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from backend.models import AnalyzeRequest, AnalyzeResponse, ErrorResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("rootcause.api")

app = FastAPI(
    title="RootCause",
    description="AI SRE agent — paste a stack trace, get a root cause diagnosis.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["POST", "OPTIONS", "GET"],
    allow_headers=["Content-Type"],
)


# In-memory rate limiter — resets on Lambda cold start, which is fine
# for a portfolio project. Production would use API Gateway usage plans.
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "10"))
_request_log: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> None:
    now = time.time()
    window = now - 60
    times = _request_log[client_ip]
    _request_log[client_ip] = [t for t in times if t > window]
    if len(_request_log[client_ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT} requests per minute.",
        )
    _request_log[client_ip].append(now)


@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Agent or API error"},
        503: {"model": ErrorResponse, "description": "Gemini API unavailable"},
    },
)
async def analyze_endpoint(req: AnalyzeRequest, request: Request):
    from backend.agent.loop import analyze
    from backend.logging.tracker import CostTracker

    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    tracker = CostTracker()

    logger.info("Analyze request: %d chars from %s", len(req.input), client_ip)
    t0 = time.perf_counter()

    try:
        result = await analyze(req.input, tracker)
    except Exception as e:
        logger.exception("Agent error")
        error_type = type(e).__name__
        if "api" in error_type.lower() or "auth" in error_type.lower() or "runtime" in error_type.lower():
            raise HTTPException(status_code=503, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    wall_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "Analyze complete: category=%s confidence=%s cost=$%.4f latency=%.0fms",
        result.get("category"),
        result.get("confidence"),
        tracker.total_cost_usd,
        wall_ms,
    )

    return result


@app.get("/health")
async def health():
    return {"status": "ok"}


handler = Mangum(app, lifespan="off")
