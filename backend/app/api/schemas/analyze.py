"""Pydantic schemas for POST /analyze."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.config import settings


class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., examples=["BTCUSDT"], description="Trading pair in the configured universe")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        return v.strip().upper()


class DecisionOut(BaseModel):
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float
    size_pct: float
    stop_loss_pct: float
    rationale: str


class SimOrderOut(BaseModel):
    run_id: str
    symbol: str
    action: str
    filled: bool
    qty: float
    price: float | None = None
    fee: float = 0.0
    notional_usd: float = 0.0
    stop_loss_pct: float | None = None
    side: str | None = None
    mid_price: float | None = None
    stale_price: bool | None = None

    model_config = {"extra": "allow"}


class RunMetadataOut(BaseModel):
    duration_ms: int = Field(..., description="Wall-clock time for the graph run")
    status: Literal["completed", "failed"] = "completed"


class AnalyzeResponse(BaseModel):
    run_id: str
    decision: DecisionOut
    sim_order: SimOrderOut | None = Field(
        default=None,
        description="Present when decision is BUY or SELL and execute ran",
    )
    metadata: RunMetadataOut


class AnalyzeStreamResponse(BaseModel):
    run_id: str = Field(..., description="Connect to WS /ws/runs/{run_id} for live events")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    detail: ErrorDetail


def validate_symbol_in_universe(symbol: str) -> None:
    allowed = settings.universe_symbols
    if symbol not in allowed:
        raise ValueError(
            f"symbol {symbol!r} is not in the configured universe: {', '.join(allowed)}"
        )
