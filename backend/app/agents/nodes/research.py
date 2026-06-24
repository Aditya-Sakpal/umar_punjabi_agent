"""Research node — gathers market/news/onchain data, runs RESEARCH prompt."""
from __future__ import annotations

from app.agents.deps import NodeDeps
from app.agents.llm import structured_llm
from app.agents.nodes._helpers import evidence_item, json_dumps, utc_now_iso
from app.agents.prompts.research import RESEARCH_SYSTEM, RESEARCH_USER, ResearchOutput
from app.agents.state import AgentState, Evidence

ONCHAIN_METRIC = "exchange_netflow"
OWNED_KEYS = frozenset({"research_brief", "evidence", "status", "errors", "revision_count"})


async def _gather_market_context(deps: NodeDeps, symbol: str) -> tuple[str, list[Evidence]]:
    """Pull tool data; tolerate individual tool failures (partial context)."""
    parts: list[str] = []
    evidence: list[Evidence] = []

    try:
        p = await deps.binance.price(symbol)
        parts.append(f"price={p['price']} USDT")
        evidence.append(
            evidence_item("binance", "spot price", p["price"], stale=bool(p.get("stale")))
        )
    except Exception:
        pass

    try:
        f = await deps.binance.funding(symbol)
        rate = f["funding_rate"]
        parts.append(f"funding={rate * 100:.4f}% [binance]")
        evidence.append(
            evidence_item(
                "binance", "funding rate", f"{rate * 100:.4f}%", stale=bool(f.get("stale"))
            )
        )
    except Exception:
        pass

    try:
        v = await deps.binance.volume(symbol)
        parts.append(
            f"24h_chg={v['price_change_pct']:+.2f}%, quote_vol={v['quote_volume']:.0f} [binance]"
        )
        evidence.append(
            evidence_item(
                "binance",
                "24h price change %",
                f"{v['price_change_pct']:+.2f}%",
                stale=bool(v.get("stale")),
            )
        )
        evidence.append(
            evidence_item(
                "binance",
                "24h quote volume",
                v["quote_volume"],
                stale=bool(v.get("stale")),
            )
        )
    except Exception:
        pass

    try:
        o = await deps.binance.ohlcv(symbol, interval="1h", limit=24)
        if o.get("candles"):
            hi = max(c["high"] for c in o["candles"])
            lo = min(c["low"] for c in o["candles"])
            parts.append(f"24h_range={lo:.2f}-{hi:.2f} [binance ohlcv]")
    except Exception:
        pass

    try:
        cg = await deps.coingecko.market(symbol)
        parts.append(
            f"mcap={cg['market_cap']:.0f}, dominance context via CG [coingecko]"
        )
        evidence.append(
            evidence_item(
                "coingecko",
                "market cap USD",
                cg["market_cap"],
                stale=bool(cg.get("stale")),
            )
        )
    except Exception:
        pass

    market = "; ".join(parts) if parts else "(market data unavailable)"
    return market, evidence


async def _gather_news(deps: NodeDeps, symbol: str) -> tuple[str, list[Evidence]]:
    evidence: list[Evidence] = []
    try:
        pack = await deps.news.headlines(symbol, limit=5)
        headlines = pack.get("headlines") or []
        for h in headlines[:5]:
            evidence.append(
                evidence_item(
                    f"news:{h.get('source', 'rss')}",
                    h.get("title", "")[:120],
                    h.get("summary", "")[:80] or None,
                    stale=bool(pack.get("stale")),
                )
            )
        return json_dumps(headlines), evidence
    except Exception:
        return "[]", evidence


async def _gather_onchain(deps: NodeDeps, symbol: str) -> tuple[str, list[Evidence]]:
    try:
        m = await deps.onchain.metric(symbol, ONCHAIN_METRIC)
        text = json_dumps(
            {"value": m["value"], "trend": m["trend"], "mock": m.get("mock", False)}
        )
        ev = evidence_item(
            f"onchain:{ONCHAIN_METRIC}",
            f"{ONCHAIN_METRIC} trend",
            m["value"],
            stale=bool(m.get("stale")),
        )
        return text, [ev]
    except Exception:
        return "{}", []


def _bump_revision_count(state: AgentState) -> dict:
    """Increment revision_count only on a repeat research pass (bounded loop gate).

    First pass leaves revision_count at 0 so route_after_research may loop once when
    evidence is thin. The second pass sets revision_count to 1, which blocks further loops.
    """
    if state.get("status") in ("research_done", "degraded:research"):
        return {"revision_count": state.get("revision_count", 0) + 1}
    return {}


def make_node(deps: NodeDeps):
    async def research_node(state: AgentState) -> dict:
        symbol = state["symbol"]
        trigger = state.get("trigger", "user")
        tool_evidence: list[Evidence] = []
        try:
            market, market_ev = await _gather_market_context(deps, symbol)
            news_json, news_ev = await _gather_news(deps, symbol)
            onchain_json, onchain_ev = await _gather_onchain(deps, symbol)
            tool_evidence = market_ev + news_ev + onchain_ev

            user = RESEARCH_USER.format(
                symbol=symbol,
                trigger=trigger,
                market=market,
                news=news_json,
                metric=ONCHAIN_METRIC,
                onchain=onchain_json,
            )
            out = await structured_llm(
                system=RESEARCH_SYSTEM,
                user=user,
                schema=ResearchOutput,
                tags=["agent:research"],
                tier="strong",
                max_tokens=1536,
            )
            return {
                "research_brief": out["research_brief"],
                "evidence": tool_evidence,
                "status": "research_done",
                **_bump_revision_count(state),
            }
        except Exception as e:
            return {
                "errors": [f"research: {e}"],
                "status": "degraded:research",
                "research_brief": (
                    f"Research degraded at {utc_now_iso()}: proceeding with thin/unverified context."
                ),
                "evidence": tool_evidence,
                **_bump_revision_count(state),
            }

    return research_node
