"""Live verification for Task 8 — compiled LangGraph routing.

Run:  uv run python scripts/verify_task8.py
Requires ANTHROPIC_API_KEY in backend/.env
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.agents.deps import build_node_deps
from app.agents.graph import (
    build_graph,
    graph_edge_list,
    graph_topology_mermaid,
    route_after_research,
)
from app.agents.nodes._helpers import conservative_risk, evidence_item, hold_decision
from app.agents.nodes.research import _bump_revision_count
from app.config import settings

SYMBOL = "BTCUSDT"
RUN_ID = "verify-task8-live"
THIN_EVIDENCE = [
    {"source": "seed", "claim": "pre-loop thin", "value": 1, "ts": "2026-06-24T12:00:00Z"}
]


def _print_section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


async def trace_node_visits(graph, state: dict) -> tuple[dict, list[str]]:
    """Return final state and ordered list of nodes that ran."""
    visited: list[str] = []
    final: dict = {}
    async for step in graph.astream(state, stream_mode="updates"):
        for node_name in step:
            visited.append(node_name)
            final = {**final, **step[node_name]}
    return final, visited


async def verify_topology(deps) -> None:
    graph = build_graph(deps)
    compiled_nodes = set(graph.get_graph().nodes.keys())
    expected = {"__start__", "research", "signal", "risk", "committee", "execute", "__end__"}
    missing = expected - compiled_nodes
    if missing:
        raise AssertionError(f"compiled graph missing nodes: {missing}")
    print(graph_topology_mermaid())
    print("\nEdge list (includes conditional branches):")
    for edge in graph_edge_list():
        print(f"  {edge[0]} -> {edge[1]}")


async def verify_happy_path_live(deps) -> dict:
    graph = build_graph(deps)
    state = {"run_id": RUN_ID, "symbol": SYMBOL, "trigger": "user", "revision_count": 0}
    final, visited = await trace_node_visits(graph, state)

    for key in ("signal", "risk", "decision"):
        if key not in final:
            raise AssertionError(f"happy path missing {key} in final state")

    print("Visited:", " -> ".join(visited))
    print("(Natural market run — decision may be HOLD; BUY/SELL execute routing proven separately.)")
    return final


async def verify_buy_execute_path_live(deps) -> dict:
    """Live upstream agents; committee stub forces BUY so execute + sim_order are proven."""

    async def committee_buy(state):
        risk = state.get("risk") or {}
        return {
            "decision": {
                "action": "BUY",
                "confidence": float(risk.get("adjusted_confidence", 0.5)),
                "size_pct": float(risk.get("suggested_size_pct", 2.0)),
                "stop_loss_pct": float(risk.get("stop_loss_pct", 2.5)),
                "rationale": "Routing proof: committee stub BUY after live signal+risk.",
            },
            "status": "committee_done",
        }

    graph = build_graph(deps, node_overrides={"committee": committee_buy})
    state = {"run_id": RUN_ID, "symbol": SYMBOL, "trigger": "user", "revision_count": 0}
    final, visited = await trace_node_visits(graph, state)

    if "execute" not in visited:
        raise AssertionError(f"BUY path must visit execute, got {visited}")
    if not final.get("sim_order", {}).get("filled"):
        raise AssertionError(f"expected filled sim_order, got {final.get('sim_order')}")
    for key in ("signal", "risk", "decision", "sim_order"):
        if key not in final:
            raise AssertionError(f"BUY path missing {key}")
    print("Visited:", " -> ".join(visited))
    return final


async def verify_hold_path_live(deps) -> dict:
    """Risk veto -> committee HOLD short-circuit -> END (no execute)."""

    async def risk_veto(state):
        return {
            "risk": {**conservative_risk(), "veto": True},
            "evidence": [
                evidence_item("binance", "funding rate (risk review)", "0.01%", stale=False)
            ],
            "status": "risk_done",
        }

    graph = build_graph(deps, node_overrides={"risk": risk_veto})
    state = {"run_id": RUN_ID, "symbol": SYMBOL, "trigger": "user", "revision_count": 0}
    final, visited = await trace_node_visits(graph, state)

    if final.get("decision", {}).get("action") != "HOLD":
        raise AssertionError(f"expected HOLD decision, got {final.get('decision')}")
    if "execute" in visited:
        raise AssertionError(f"execute must not run on HOLD path, visited={visited}")
    if "sim_order" in final:
        raise AssertionError("sim_order must be absent on HOLD path")
    print("Visited:", " -> ".join(visited))
    print("Decision:", json.dumps(final["decision"], indent=2))
    return final


async def verify_bounded_loop(deps) -> dict:
    """Thin evidence stub forces one extra research pass; revision_count blocks a third."""
    visits: list[dict] = []

    async def thin_research(state):
        entry = {
            "visit": len(visits) + 1,
            "revision_count_before": state.get("revision_count", 0),
            "status_before": state.get("status"),
            "evidence_len_before": len(state.get("evidence", [])),
        }
        visits.append(entry)
        patch = {
            "research_brief": f"thin brief pass {len(visits)}",
            "evidence": list(THIN_EVIDENCE),
            "status": "research_done",
        }
        patch.update(_bump_revision_count(state))
        return patch

    async def passthrough_signal(state):
        from app.agents.nodes import signal as signal_mod

        return await signal_mod.make_node(deps)(state)

    graph = build_graph(
        deps,
        node_overrides={"research": thin_research, "signal": passthrough_signal},
    )
    initial = {
        "run_id": RUN_ID,
        "symbol": SYMBOL,
        "trigger": "user",
        "revision_count": 0,
        "evidence": [],
    }
    print("Initial revision_count:", initial["revision_count"])
    print("route_after_research (pre-run, thin seed):", route_after_research(initial))

    final, visited = await trace_node_visits(graph, initial)
    research_count = visited.count("research")

    print("Research visits:", research_count)
    for v in visits:
        print(f"  pass {v['visit']}: rc_before={v['revision_count_before']}, "
              f"status_before={v['status_before']!r}, evidence_len={v['evidence_len_before']}")
    print("Final revision_count:", final.get("revision_count"))
    print("Visited:", " -> ".join(visited))

    if research_count != 2:
        raise AssertionError(f"expected exactly 2 research passes, got {research_count}")
    if final.get("revision_count") != 1:
        raise AssertionError(f"expected final revision_count=1, got {final.get('revision_count')}")
    if visits[1]["revision_count_before"] != 0:
        raise AssertionError("second pass should enter with revision_count still 0")
    if visits[1]["status_before"] not in ("research_done", "degraded:research"):
        raise AssertionError("second pass should see prior research status")

    return {"visits": visits, "final": final, "visited": visited}


async def verify_no_infinite_loop(deps) -> None:
    """Persistently thin evidence + revision_count gate must always terminate."""
    calls = 0

    async def eternally_thin_research(state):
        nonlocal calls
        calls += 1
        if calls > 5:
            raise AssertionError("infinite loop detected — research ran more than 5 times")
        patch = {
            "research_brief": "still thin",
            "evidence": list(THIN_EVIDENCE),
            "status": "research_done",
        }
        patch.update(_bump_revision_count(state))
        return patch

    async def quick_signal(state):
        from app.agents.nodes._helpers import hold_signal

        return {"signal": hold_signal(), "status": "signal_done"}

    async def quick_risk(state):
        return {"risk": conservative_risk(), "status": "risk_done"}

    async def quick_committee(state):
        return {"decision": hold_decision(), "status": "committee_done"}

    graph = build_graph(
        deps,
        node_overrides={
            "research": eternally_thin_research,
            "signal": quick_signal,
            "risk": quick_risk,
            "committee": quick_committee,
        },
    )
    await graph.ainvoke(
        {"run_id": RUN_ID, "symbol": SYMBOL, "trigger": "user", "revision_count": 0}
    )
    assert calls == 2, f"expected 2 research calls, got {calls}"
    print(f"Terminated after {calls} research passes (revision_count gate holds)")


async def main() -> int:
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return 1
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    deps = await build_node_deps()
    failures: list[str] = []

    try:
        _print_section("TOPOLOGY — compiled graph structure")
        await verify_topology(deps)

        _print_section("HAPPY PATH (live ainvoke — natural decision)")
        happy = await verify_happy_path_live(deps)
        print("signal.direction:", happy["signal"]["direction"])
        print("decision:", json.dumps(happy["decision"], indent=2))

        _print_section("BUY EXECUTE PATH (live upstream + committee BUY stub)")
        buy_final = await verify_buy_execute_path_live(deps)
        print("decision.action:", buy_final["decision"]["action"])
        print("sim_order:", json.dumps(buy_final["sim_order"], indent=2))

        _print_section("HOLD PATH — risk veto -> committee HOLD -> END (no execute)")
        await verify_hold_path_live(deps)

        _print_section("BOUNDED RESEARCH LOOP (thin evidence stub + live signal)")
        await verify_bounded_loop(deps)

        _print_section("NO INFINITE LOOP (persistently thin evidence)")
        await verify_no_infinite_loop(deps)

    except Exception as e:
        failures.append(str(e))
        print(f"FAIL: {e}")
    finally:
        await deps.aclose()

    _print_section("SUMMARY")
    if failures:
        print("FAILED:", failures)
        return 1
    print("ALL ACCEPTANCE CRITERIA PASSED")
    print(
        "\nrevision_count design: incremented inside research node only on a repeat pass "
        "(status already research_done/degraded). First pass leaves rc=0; router may loop "
        "once when evidence<3; second pass sets rc=1; router always exits to signal thereafter."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
