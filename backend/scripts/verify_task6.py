"""Live verification for Task 6 agent prompts.

Run:  uv run python scripts/verify_task6.py
Requires ANTHROPIC_API_KEY in backend/.env
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Ensure backend root is on path when run as script
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents import llm as llm_mod
from app.agents.prompts.committee import COMMITTEE_SYSTEM, COMMITTEE_USER
from app.agents.prompts.research import RESEARCH_SYSTEM, RESEARCH_USER, ResearchOutput
from app.agents.prompts.risk import RISK_SYSTEM, RISK_USER
from app.agents.prompts.signal import SIGNAL_SYSTEM, SIGNAL_USER
from app.agents.prompts.watcher import WATCHER_SYSTEM, WATCHER_USER, WatcherOutput
from app.agents.state import Decision, RiskAssessment, Signal
from app.config import settings

# --- sample inputs (realistic demo fixtures) ---------------------------------

WATCHER_SNAPSHOT = """\
BTCUSDT | trigger: funding_spike | price_chg_24h: +4.2% | funding: 0.078% | vol_vs_avg: 2.1x
ETHUSDT | trigger: volume_surge | price_chg_24h: +1.8% | funding: 0.011% | vol_vs_avg: 3.4x"""

RESEARCH_INPUTS = {
    "symbol": "BTCUSDT",
    "trigger": "user",
    "market": (
        "price=97250 USDT, 24h_high=98100, 24h_low=94800, 24h_chg=+4.2%, "
        "funding=0.078% [binance], volume_24h=28.4B vs 7d_avg=19.1B"
    ),
    "news": (
        '[{"title": "Bitcoin ETF inflows hit 3-week high", "source": "coindesk", "ts": "2026-06-24T08:00Z"}, '
        '{"title": "Fed minutes hint delayed cuts", "source": "reuters", "ts": "2026-06-24T06:30Z"}]'
    ),
    "metric": "exchange_netflow",
    "onchain": '{"value": -12400, "trend": "outflow", "unit": "BTC"}',
}

SIGNAL_INPUTS = {
    "research_brief": (
        "BTC broke above 96k on 2.1x average volume with funding at 0.078% [binance] — "
        "elevated but not extreme. ETF inflow headline is supportive [coindesk]; Fed minutes "
        "are a headwind [reuters]. On-chain net outflow (-12.4k BTC) suggests accumulation "
        "off exchanges. Conflicting: momentum bullish, macro cautious."
    ),
    "evidence": (
        '[{"source": "binance", "claim": "24h volume vs 7d avg", "value": "2.1x", "ts": "2026-06-24T12:00Z"}, '
        '{"source": "binance", "claim": "funding rate", "value": "0.078%", "ts": "2026-06-24T12:00Z"}, '
        '{"source": "news:coindesk", "claim": "ETF inflows 3-week high", "value": null, "ts": "2026-06-24T08:00Z"}]'
    ),
    "historical_setups": (
        "Similar setup observed 4 days ago.\n\nSignal:\nBUY\n\nOutcome:\n+3.2%"
    ),
}

# Crowded long setup — Risk headline proof
RISK_SIGNAL = {
    "direction": "BUY",
    "confidence": 0.72,
    "thesis": "Momentum breakout above 96k with ETF tailwind; funding elevated but trend intact.",
    "horizon": "intraday",
}

RISK_INPUTS = {
    "signal": json.dumps(RISK_SIGNAL),
    "evidence": SIGNAL_INPUTS["evidence"],
    "funding": "0.085% (elevated positive — longs paying shorts, 95th percentile 30d)",
    "vol": "24h realized vol 8.2% vs 30d avg 3.1% (2.6x spike)",
    "portfolio": '{"equity_usd": 100000, "btc_exposure_pct": 35, "open_positions": 2}',
}

COMMITTEE_SIGNAL = RISK_SIGNAL
COMMITTEE_RISK = {
    "concerns": [
        "Funding at 0.085% signals crowded longs — 95th percentile; squeeze risk on reversal.",
        "Realized vol 8.2% vs 3.1% avg implies stop runs; 2.6x spike reduces edge on breakout chase.",
    ],
    "adjusted_confidence": 0.48,
    "suggested_size_pct": 2.5,
    "stop_loss_pct": 3.5,
    "veto": False,
}

COMMITTEE_INPUTS = {
    "signal": json.dumps(COMMITTEE_SIGNAL),
    "risk": json.dumps(COMMITTEE_RISK),
    "evidence": SIGNAL_INPUTS["evidence"],
}


async def raw_llm_text(*, system: str, user: str, tier: llm_mod.Tier, max_tokens: int = 1024) -> str:
    llm = llm_mod.make_llm(tier, streaming=False, max_tokens=max_tokens)
    resp = await llm.ainvoke(
        [SystemMessage(content=system), HumanMessage(content=user)],
        config={"tags": [f"agent:verify"]},
    )
    return llm_mod._content_to_text(resp.content)


def prose_before_json(text: str) -> tuple[str, dict]:
    data = llm_mod._extract_json_object(text)
    start = text.find("{")
    prose = text[:start].strip() if start > 0 else ""
    return prose, data


def _mentions_number(text: str, *needles: str) -> bool:
    lower = text.lower()
    return any(n.lower() in lower for n in needles)


async def verify_watcher() -> dict:
    user = WATCHER_USER.format(snapshot=WATCHER_SNAPSHOT)
    raw = await raw_llm_text(system=WATCHER_SYSTEM, user=user, tier="cheap")
    prose, data = prose_before_json(raw)
    parsed = llm_mod._coerce_to_schema(data, WatcherOutput)
    opps = parsed["opportunities"]
    assert isinstance(opps, list) and len(opps) >= 1
    for o in opps:
        assert {"symbol", "trigger_type", "summary", "salience"} <= set(o.keys())
    return {"raw": raw, "parsed": parsed, "prose_len": len(prose)}


async def verify_research() -> dict:
    user = RESEARCH_USER.format(**RESEARCH_INPUTS)
    raw = await raw_llm_text(system=RESEARCH_SYSTEM, user=user, tier="strong", max_tokens=1536)
    prose, data = prose_before_json(raw)
    parsed = llm_mod._coerce_to_schema(data, ResearchOutput)
    assert parsed["data_quality"] in ("good", "partial", "thin")
    assert isinstance(parsed["key_points"], list) and len(parsed["key_points"]) >= 1
    return {"raw": raw, "parsed": parsed, "prose_len": len(prose)}


async def verify_signal() -> dict:
    user = SIGNAL_USER.format(**SIGNAL_INPUTS)
    parsed = await llm_mod.structured_llm(
        system=SIGNAL_SYSTEM, user=user, schema=Signal, tags=["agent:signal"], tier="strong"
    )
    raw = await raw_llm_text(system=SIGNAL_SYSTEM, user=user, tier="strong")
    return {"raw": raw, "parsed": parsed}


async def verify_risk() -> dict:
    user = RISK_USER.format(**RISK_INPUTS)
    raw = await raw_llm_text(system=RISK_SYSTEM, user=user, tier="strong", max_tokens=1536)
    prose, data = prose_before_json(raw)
    parsed = llm_mod._coerce_to_schema(data, RiskAssessment)

    concerns_text = " ".join(parsed["concerns"])
    specific = _mentions_number(
        concerns_text, "0.085", "0.085%", "8.2", "8.2%", "3.1", "funding", "vol"
    )
    conf_ok = parsed["adjusted_confidence"] < RISK_SIGNAL["confidence"]
    size_ok = 0 < parsed["suggested_size_pct"] <= 10
    stop_ok = 0 < parsed["stop_loss_pct"] <= 15

    return {
        "raw": raw,
        "parsed": parsed,
        "prose": prose,
        "checks": {
            "specific_concern": specific,
            "confidence_reduced": conf_ok,
            "sane_size_pct": size_ok,
            "sane_stop_loss_pct": stop_ok,
        },
    }


async def verify_committee() -> dict:
    user = COMMITTEE_USER.format(**COMMITTEE_INPUTS)
    raw = await raw_llm_text(system=COMMITTEE_SYSTEM, user=user, tier="strong", max_tokens=1536)
    prose, data = prose_before_json(raw)
    parsed = llm_mod._coerce_to_schema(data, Decision)

    rationale = parsed["rationale"].lower()
    acknowledges = any(
        w in rationale
        for w in ("risk", "disagree", "however", "although", "pushback", "concern", "crowded", "funding")
    )
    respects_size = abs(parsed["size_pct"] - COMMITTEE_RISK["suggested_size_pct"]) <= 1.5
    respects_stop = abs(parsed["stop_loss_pct"] - COMMITTEE_RISK["stop_loss_pct"]) <= 1.5

    return {
        "raw": raw,
        "parsed": parsed,
        "checks": {
            "rationale_acknowledges_disagreement": acknowledges,
            "respects_risk_size": respects_size,
            "respects_risk_stop": respects_stop,
        },
    }


async def verify_streaming_prose() -> dict:
    """Prove think-out-loud-then-JSON via streamed token assembly (risk agent)."""
    user = RISK_USER.format(**RISK_INPUTS)
    chunks: list[str] = []
    async for delta in llm_mod.stream_tokens(
        system=RISK_SYSTEM, user=user, agent="risk", tier="strong", max_tokens=1536
    ):
        chunks.append(delta)
    full = "".join(chunks)
    prose, data = prose_before_json(full)
    parsed = llm_mod._coerce_to_schema(data, RiskAssessment)
    json_start = full.find("{")
    return {
        "streamed_full": full,
        "prose_before_json": prose,
        "json_start_index": json_start,
        "prose_chars": len(prose),
        "parsed": parsed,
        "ok": json_start > 80 and len(prose) > 50,
    }


def _print_section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


async def main() -> int:
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        return 1

    # Windows consoles often default to cp1252; force UTF-8 for model output.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    failures: list[str] = []

    _print_section("WATCHER (cheap tier)")
    w = await verify_watcher()
    print("RAW:\n", w["raw"][:1200], "..." if len(w["raw"]) > 1200 else "")
    print("\nPARSED:", json.dumps(w["parsed"], indent=2))

    _print_section("RESEARCH (strong tier)")
    r = await verify_research()
    print("RAW:\n", r["raw"][:1200], "..." if len(r["raw"]) > 1200 else "")
    print("\nPARSED:", json.dumps(r["parsed"], indent=2))

    _print_section("SIGNAL (strong tier)")
    s = await verify_signal()
    print("RAW:\n", s["raw"][:1200], "..." if len(s["raw"]) > 1200 else "")
    print("\nPARSED:", json.dumps(s["parsed"], indent=2))

    _print_section("RISK — specificity proof (strong tier)")
    risk = await verify_risk()
    print("RAW:\n", risk["raw"])
    print("\nPARSED:", json.dumps(risk["parsed"], indent=2))
    print("\nCHECKS:", json.dumps(risk["checks"], indent=2))
    print(f"\nSignal confidence: {RISK_SIGNAL['confidence']}")
    print(f"Adjusted confidence: {risk['parsed']['adjusted_confidence']}")
    print("Concerns:")
    for c in risk["parsed"]["concerns"]:
        print(f"  - {c}")
    for k, v in risk["checks"].items():
        if not v:
            failures.append(f"risk.{k}")

    _print_section("COMMITTEE — disagreement resolution (strong tier)")
    c = await verify_committee()
    print("RAW:\n", c["raw"])
    print("\nPARSED:", json.dumps(c["parsed"], indent=2))
    print("\nCHECKS:", json.dumps(c["checks"], indent=2))
    for k, v in c["checks"].items():
        if not v:
            failures.append(f"committee.{k}")

    _print_section("STREAMING — prose before JSON (risk agent)")
    stream = await verify_streaming_prose()
    print(f"JSON starts at char {stream['json_start_index']}, prose chars={stream['prose_chars']}")
    print("PROSE (excerpt):", stream["prose_before_json"][:500], "...")
    print("PARSED keys:", list(stream["parsed"].keys()))
    if not stream["ok"]:
        failures.append("streaming.prose_before_json")

    _print_section("SUMMARY")
    if failures:
        print("FAILED:", ", ".join(failures))
        return 1
    print("ALL ACCEPTANCE CRITERIA PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
