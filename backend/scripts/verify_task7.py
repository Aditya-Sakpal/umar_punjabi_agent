"""Live verification for Task 7 graph nodes.

Run:  uv run python scripts/verify_task7.py
Requires ANTHROPIC_API_KEY in backend/.env
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch as mock_patch

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.agents import llm as llm_mod
from app.agents.deps import NodeDeps, build_node_deps
from app.agents.nodes import committee, execute, memory_recall, research, risk, signal
from app.agents.nodes._helpers import hold_decision
from app.agents.prompts.signal import SIGNAL_SYSTEM, SIGNAL_USER
from app.agents.state import AgentState, Decision
from app.config import settings
from app.services.paper_engine import PaperEngine

SYMBOL = "BTCUSDT"
RUN_ID = "verify-task7-live"


def _print_section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def apply_patch(state: AgentState, patch: dict) -> AgentState:
    """Simulate LangGraph reducers for evidence/errors append."""
    out: dict[str, Any] = dict(state)
    for key, val in patch.items():
        if key in ("evidence", "errors"):
            out[key] = list(out.get(key, [])) + list(val)
        else:
            out[key] = val
    return out  # type: ignore[return-value]


def assert_owned_only(patch: dict, owned: frozenset[str], node: str) -> None:
    extra = set(patch) - owned
    if extra:
        raise AssertionError(f"{node} returned unexpected keys: {extra}")


async def chain_happy_path(deps: NodeDeps) -> AgentState:
    state: AgentState = {"run_id": RUN_ID, "symbol": SYMBOL, "trigger": "user"}

    r_node = research.make_node(deps)
    m_node = memory_recall.make_node(deps)
    s_node = signal.make_node(deps)
    k_node = risk.make_node(deps)
    c_node = committee.make_node(deps)
    x_node = execute.make_node(deps)

    for name, node, owned in [
        ("research", r_node, research.OWNED_KEYS),
        ("memory_recall", m_node, memory_recall.OWNED_KEYS),
        ("signal", s_node, signal.OWNED_KEYS),
        ("risk", k_node, risk.OWNED_KEYS),
        ("committee", c_node, committee.OWNED_KEYS),
        ("execute", x_node, execute.OWNED_KEYS),
    ]:
        patch = await node(state)
        assert_owned_only(patch, owned, name)
        state = apply_patch(state, patch)
        print(f"  {name}: status={patch.get('status')} keys={sorted(patch.keys())}")

    return state


async def verify_degrade_research(deps: NodeDeps) -> dict:
    state: AgentState = {"run_id": RUN_ID, "symbol": SYMBOL, "trigger": "user"}
    node = research.make_node(deps)
    with mock_patch(
        "app.agents.nodes.research.structured_llm",
        new_callable=AsyncMock,
        side_effect=RuntimeError("injected LLM failure"),
    ):
        result = await node(state)
    assert_owned_only(result, research.OWNED_KEYS, "research")
    assert result["status"] == "degraded:research"
    assert result.get("errors")
    assert "research_brief" in result
    return result


async def verify_degrade_risk(deps: NodeDeps) -> dict:
    state: AgentState = {
        "run_id": RUN_ID,
        "symbol": SYMBOL,
        "trigger": "user",
        "research_brief": "stub brief",
        "signal": {
            "direction": "BUY",
            "confidence": 0.7,
            "thesis": "stub",
            "horizon": "intraday",
        },
        "evidence": [],
    }

    class FailingFundingBinance:
        def __init__(self, inner):
            self._inner = inner

        async def funding(self, symbol: str):
            raise ConnectionError("injected funding API failure")

        def __getattr__(self, name: str):
            return getattr(self._inner, name)

    broken_deps = NodeDeps(
        binance=FailingFundingBinance(deps.binance),  # type: ignore[arg-type]
        coingecko=deps.coingecko,
        news=deps.news,
        onchain=deps.onchain,
        paper_engine=deps.paper_engine,
        memory=deps.memory,
    )
    node = risk.make_node(broken_deps)
    patch = await node(state)
    assert_owned_only(patch, risk.OWNED_KEYS, "risk")
    assert patch["status"] == "degraded:risk"
    assert patch.get("errors")
    assert patch.get("risk")
    return patch


async def verify_evidence_accumulation(deps: NodeDeps) -> list:
    state: AgentState = {"run_id": RUN_ID, "symbol": SYMBOL, "trigger": "user"}
    r_patch = await research.make_node(deps)(state)
    state = apply_patch(state, r_patch)
    s_patch = await signal.make_node(deps)(state)
    state = apply_patch(state, s_patch)
    k_patch = await risk.make_node(deps)(state)
    state = apply_patch(state, k_patch)
    evidence = state.get("evidence", [])
    sources = {e["source"] for e in evidence}
    has_research = any(
        s.startswith(("binance", "coingecko", "news:", "onchain:")) for s in sources
    )
    has_risk_funding = any("risk review" in e.get("claim", "") for e in evidence)
    if len(evidence) < 2 or not has_research or not has_risk_funding:
        raise AssertionError(
            f"evidence did not accumulate from research+risk: {len(evidence)} items, sources={sources}"
        )
    return evidence


async def verify_execute_paths(deps: NodeDeps) -> tuple[dict, dict]:
    x_node = execute.make_node(deps)

    buy_decision: Decision = {
        "action": "BUY",
        "confidence": 0.55,
        "size_pct": 2.5,
        "stop_loss_pct": 3.0,
        "rationale": "verification BUY",
    }
    buy_state: AgentState = {
        "run_id": RUN_ID,
        "symbol": SYMBOL,
        "decision": buy_decision,
    }
    buy_patch = await x_node(buy_state)
    assert_owned_only(buy_patch, execute.OWNED_KEYS, "execute")
    buy_order = buy_patch["sim_order"]
    if not buy_order.get("filled") or not buy_order.get("price") or buy_order.get("qty", 0) <= 0:
        raise AssertionError(f"BUY sim_order invalid: {buy_order}")

    hold_state: AgentState = {
        "run_id": RUN_ID,
        "symbol": SYMBOL,
        "decision": hold_decision(),
    }
    hold_patch = await x_node(hold_state)
    hold_order = hold_patch["sim_order"]
    if hold_order.get("filled") or hold_order.get("qty", 0) != 0:
        raise AssertionError(f"HOLD sim_order should be no-op: {hold_order}")

    return buy_order, hold_order


async def verify_tag_check() -> dict:
    """Signal-agent streaming must carry agent:signal on token events."""
    user = SIGNAL_USER.format(
        research_brief="BTC +3% on volume; funding 0.05% [binance].",
        evidence='[{"source":"binance","claim":"funding","value":"0.05%","ts":"t"}]',
    )
    tagged = 0
    prose: list[str] = []
    async for event in llm_mod.iter_token_events(
        system=SIGNAL_SYSTEM, user=user, agent="signal", tier="strong", max_tokens=512
    ):
        if event["event"] == "on_chat_model_stream":
            if "agent:signal" in (event.get("tags") or []):
                tagged += 1
            delta = llm_mod._content_to_text(event["data"]["chunk"].content)
            if delta:
                prose.append(delta)
    full = "".join(prose)
    json_start = full.find("{")
    return {
        "tagged_stream_events": tagged,
        "prose_chars_before_json": json_start,
        "ok": tagged > 0 and json_start > 40,
    }


async def main() -> int:
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return 1
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    failures: list[str] = []
    deps = await build_node_deps()

    try:
        _print_section("HAPPY PATH — research → signal → risk → committee → execute")
        final = await chain_happy_path(deps)
        print("\nDECISION:", json.dumps(final.get("decision"), indent=2))
        print("SIM_ORDER:", json.dumps(final.get("sim_order"), indent=2))

        _print_section("EVIDENCE ACCUMULATION — research → signal → risk")
        ev = await verify_evidence_accumulation(deps)
        print(f"Total evidence items: {len(ev)}")
        for item in ev:
            print(f"  [{item['source']}] {item['claim']}: {item['value']}")

        _print_section("DEGRADE — research (injected LLM failure)")
        r_deg = await verify_degrade_research(deps)
        print(json.dumps(r_deg, indent=2, default=str))

        _print_section("DEGRADE — risk (injected funding tool failure)")
        k_deg = await verify_degrade_risk(deps)
        print(json.dumps(k_deg, indent=2, default=str))

        _print_section("EXECUTE — BUY fill vs HOLD no-op")
        buy_order, hold_order = await verify_execute_paths(deps)
        print("BUY:", json.dumps(buy_order, indent=2))
        print("HOLD:", json.dumps(hold_order, indent=2))
        print(
            f"\nPaperEngine notional assumption: equity=${deps.paper_engine.equity_usd:,.0f}, "
            f"size_pct=2.5% → notional=${buy_order['notional_usd']}"
        )

        _print_section("TAG CHECK — agent:signal on streamed tokens")
        tag = await verify_tag_check()
        print(json.dumps(tag, indent=2))
        if not tag["ok"]:
            failures.append("tag_check")

    finally:
        await deps.aclose()

    _print_section("SUMMARY")
    if failures:
        print("FAILED:", ", ".join(failures))
        return 1
    print("ALL ACCEPTANCE CRITERIA PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
