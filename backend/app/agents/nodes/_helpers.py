"""Shared helpers for graph nodes — timestamps, safe defaults, evidence builders."""
from __future__ import annotations

import datetime as dt
import json
import math
import statistics

from app.agents.state import Decision, Evidence, RiskAssessment, Signal


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def evidence_item(
    source: str, claim: str, value: str | float | None, *, stale: bool = False
) -> Evidence:
    val: str | float | None = value
    if stale and isinstance(val, (int, float)):
        val = f"{val} (stale)"
    elif stale and val is not None:
        val = f"{val} (stale)"
    return {"source": source, "claim": claim, "value": val, "ts": utc_now_iso()}


def conservative_risk() -> RiskAssessment:
    return {
        "concerns": ["Risk assessment unavailable — defaulting to minimal size and wide stop."],
        "adjusted_confidence": 0.25,
        "suggested_size_pct": 1.0,
        "stop_loss_pct": 5.0,
        "veto": False,
    }


def hold_signal() -> Signal:
    return {
        "direction": "HOLD",
        "confidence": 0.3,
        "thesis": "Insufficient conviction — holding flat pending better data.",
        "horizon": "intraday",
    }


def hold_decision(*, rationale: str | None = None) -> Decision:
    return {
        "action": "HOLD",
        "confidence": 0.3,
        "size_pct": 0.0,
        "stop_loss_pct": 0.0,
        "rationale": rationale
        or "Committee could not reconcile signal and risk — standing aside.",
    }


def format_volatility(ohlcv: dict) -> str:
    candles = ohlcv.get("candles") or []
    if len(candles) < 3:
        return "unavailable (insufficient OHLCV)"
    closes = [float(c["close"]) for c in candles[-24:]]
    returns = [(closes[i] / closes[i - 1] - 1.0) for i in range(1, len(closes))]
    if len(returns) < 2:
        return "unavailable"
    vol_pct = statistics.stdev(returns) * 100.0
    # Scale to approximate 24h realized vol (hourly bars)
    realized_24h = vol_pct * math.sqrt(min(len(returns), 24))
    return f"{realized_24h:.2f}% realized (from {len(returns)} hourly returns)"


def json_dumps(obj: object) -> str:
    return json.dumps(obj, default=str)
