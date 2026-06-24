"""Unit tests for graph routing (mocked nodes — no network)."""
from __future__ import annotations

import pytest

from app.agents.deps import NodeDeps
from app.agents.graph import (
    build_graph,
    route_after_committee,
    route_after_research,
)
from app.agents.nodes._helpers import conservative_risk, hold_decision, hold_signal
from app.agents.nodes.research import _bump_revision_count
from app.services.paper_engine import PaperEngine


from tests.stubs import StubMemoryTool


class StubBinance:
    async def price(self, symbol: str) -> dict:
        return {"price": 100.0, "stale": False}


def _deps() -> NodeDeps:
    b = StubBinance()
    return NodeDeps(
        binance=b,  # type: ignore[arg-type]
        coingecko=b,  # type: ignore[arg-type]
        news=b,  # type: ignore[arg-type]
        onchain=b,  # type: ignore[arg-type]
        paper_engine=PaperEngine(b),  # type: ignore[arg-type]
        memory=StubMemoryTool(),  # type: ignore[arg-type]
    )


THIN = [{"source": "stub", "claim": "x", "value": 1, "ts": "t"}]


def test_route_after_research_loops_once_gate():
    assert route_after_research({"evidence": THIN, "revision_count": 0}) == "research"
    assert route_after_research({"evidence": THIN, "revision_count": 1}) == "memory_recall"
    assert route_after_research({"evidence": THIN * 3, "revision_count": 0}) == "memory_recall"


def test_route_after_committee():
    assert route_after_committee({"decision": {"action": "BUY"}}) == "execute"
    assert route_after_committee({"decision": {"action": "HOLD"}}) == "end"
    assert route_after_committee({"decision": hold_decision()}) == "end"


def test_bump_revision_only_on_repeat():
    assert _bump_revision_count({}) == {}
    assert _bump_revision_count({"status": "research_done", "revision_count": 0}) == {
        "revision_count": 1
    }


@pytest.mark.asyncio
async def test_bounded_research_loop_at_most_two_visits():
    visits: list[int] = []

    async def thin_research(state):
        visits.append(state.get("revision_count", 0))
        patch = {
            "research_brief": "thin",
            "evidence": list(THIN),
            "status": "research_done",
        }
        patch.update(
            {"revision_count": state.get("revision_count", 0) + 1}
            if state.get("status") in ("research_done", "degraded:research")
            else {}
        )
        return patch

    async def stub_memory(state):
        return {"similar_memories": [], "status": "memory_recall_done"}

    async def stub_signal(state):
        return {"signal": hold_signal(), "status": "signal_done"}

    async def stub_risk(state):
        return {"risk": conservative_risk(), "status": "risk_done"}

    async def stub_committee(state):
        return {"decision": hold_decision(), "status": "committee_done"}

    graph = build_graph(
        _deps(),
        node_overrides={
            "research": thin_research,
            "memory_recall": stub_memory,
            "signal": stub_signal,
            "risk": stub_risk,
            "committee": stub_committee,
        },
    )
    final = await graph.ainvoke(
        {"run_id": "t", "symbol": "BTCUSDT", "trigger": "user", "revision_count": 0}
    )
    assert len(visits) == 2
    assert visits == [0, 0]
    assert final.get("revision_count") == 1
    assert "sim_order" not in final


@pytest.mark.asyncio
async def test_hold_path_skips_execute():
    async def stub_research(state):
        return {
            "research_brief": "ok",
            "evidence": THIN * 3,
            "status": "research_done",
        }

    async def stub_memory(state):
        return {"similar_memories": [], "status": "memory_recall_done"}

    async def stub_signal(state):
        return {"signal": hold_signal(), "status": "signal_done"}

    async def stub_risk(state):
        return {"risk": {**conservative_risk(), "veto": True}, "status": "risk_done"}

    graph = build_graph(
        _deps(),
        node_overrides={
            "research": stub_research,
            "memory_recall": stub_memory,
            "signal": stub_signal,
            "risk": stub_risk,
        },
    )
    final = await graph.ainvoke({"run_id": "t", "symbol": "BTCUSDT", "trigger": "user"})
    assert final["decision"]["action"] == "HOLD"
    assert "sim_order" not in final


@pytest.mark.asyncio
async def test_buy_path_reaches_execute():
    async def stub_research(state):
        return {
            "research_brief": "ok",
            "evidence": THIN * 3,
            "status": "research_done",
        }

    async def stub_memory(state):
        return {"similar_memories": [], "status": "memory_recall_done"}

    async def stub_signal(state):
        return {
            "signal": {
                "direction": "BUY",
                "confidence": 0.6,
                "thesis": "t",
                "horizon": "intraday",
            },
            "status": "signal_done",
        }

    async def stub_risk(state):
        return {"risk": conservative_risk(), "status": "risk_done"}

    async def stub_committee(state):
        return {
            "decision": {
                "action": "BUY",
                "confidence": 0.5,
                "size_pct": 2.0,
                "stop_loss_pct": 2.0,
                "rationale": "go",
            },
            "status": "committee_done",
        }

    graph = build_graph(
        _deps(),
        node_overrides={
            "research": stub_research,
            "memory_recall": stub_memory,
            "signal": stub_signal,
            "risk": stub_risk,
            "committee": stub_committee,
        },
    )
    final = await graph.ainvoke({"run_id": "t", "symbol": "BTCUSDT", "trigger": "user"})
    assert final.get("sim_order", {}).get("filled") is True
