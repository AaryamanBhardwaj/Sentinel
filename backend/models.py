"""Request/response models for the RootCause API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    input: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Log snippet, stack trace, or error message to diagnose.",
    )


class CostMeta(BaseModel):
    api_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_latency_ms: float
    total_cost_usd: float
    tool_calls_made: int


class AnalyzeResponse(BaseModel):
    root_cause: str
    confidence: str
    category: str
    explanation: str
    fix: str
    references: List[str] = []
    meta: Optional[CostMeta] = Field(None, alias="_meta")

    class Config:
        populate_by_name = True


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
