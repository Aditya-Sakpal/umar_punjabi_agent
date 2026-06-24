"""LangGraph assembly — deep chain with bounded research loop + committee gate."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.deps import NodeDeps
from app.agents.nodes import committee, execute, memory_recall, research, risk, signal
from app.agents.state import AgentState

NodeFn = Callable[[AgentState], Awaitable[dict[str, Any]]]


def route_after_research(state: AgentState) -> str:
    thin = len(state.get("evidence", [])) < 3
    if thin and state.get("revision_count", 0) < 1:
        return "research"
    return "memory_recall"


def route_after_committee(state: AgentState) -> str:
    action = state.get("decision", {}).get("action")
    return "execute" if action in ("BUY", "SELL") else "end"


def graph_topology_mermaid() -> str:
    """Blueprint topology (Part 3.2) for docs and verification output."""
    return """\
flowchart TD
    START([START]) --> R[research]
    R -->|evidence thin & revision_count<1| R
    R -->|enough or revision_count>=1| M[memory_recall]
    M --> S[signal]
    S --> K[risk]
    K --> C[committee]
    C -->|HOLD / veto| E1([END])
    C -->|BUY / SELL| X[execute]
    X --> E2([END])"""


def graph_edge_list() -> list[tuple[str, str]]:
    return [
        ("__start__", "research"),
        ("research", "research"),
        ("research", "memory_recall"),
        ("memory_recall", "signal"),
        ("signal", "risk"),
        ("risk", "committee"),
        ("committee", "execute"),
        ("committee", "__end__"),
        ("execute", "__end__"),
    ]


def graph_info() -> dict[str, Any]:
    """Lightweight graph introspection for LangFuse, Trace View, and debugging."""
    static_edges = [
        {"from": "signal", "to": "risk"},
        {"from": "execute", "to": "__end__"},
    ]
    conditional_edges = [
        {
            "from": "__start__",
            "to": "research",
            "router": None,
        },
        {
            "from": "research",
            "router": "route_after_research",
            "map": {"research": "research", "memory_recall": "memory_recall"},
        },
        {
            "from": "committee",
            "router": "route_after_committee",
            "map": {"execute": "execute", "end": "__end__"},
        },
    ]
    loop_edges = [
        {"from": "research", "to": "research", "when": "thin evidence & revision_count<1"},
        {"from": "research", "to": "memory_recall", "when": "enough evidence or revision_count>=1"},
        {"from": "memory_recall", "to": "signal"},
        {"from": "committee", "to": "execute", "when": "decision.action in BUY|SELL"},
        {"from": "committee", "to": "__end__", "when": "HOLD or veto"},
    ]
    return {
        "nodes": ["research", "memory_recall", "signal", "risk", "committee", "execute"],
        "edges": static_edges + loop_edges,
        "conditional_edges": conditional_edges,
        "routing": {
            "route_after_research": {
                "research": "evidence < 3 and revision_count < 1",
                "memory_recall": "otherwise",
            },
            "route_after_committee": {
                "execute": "decision.action in (BUY, SELL)",
                "end": "HOLD or veto",
            },
        },
    }


def build_graph(
    deps: NodeDeps,
    *,
    node_overrides: dict[str, NodeFn] | None = None,
):
    """Wire Task-7 nodes into a compiled LangGraph.

    ``node_overrides`` maps node name -> async node callable (for routing proofs).
    """
    overrides = node_overrides or {}

    def _node(name: str, factory: Callable[[NodeDeps], NodeFn]) -> NodeFn:
        if name in overrides:
            return overrides[name]
        return factory(deps)

    g = StateGraph(AgentState)
    g.add_node("research", _node("research", research.make_node))
    g.add_node("memory_recall", _node("memory_recall", memory_recall.make_node))
    g.add_node("signal", _node("signal", signal.make_node))
    g.add_node("risk", _node("risk", risk.make_node))
    g.add_node("committee", _node("committee", committee.make_node))
    g.add_node("execute", _node("execute", execute.make_node))

    g.add_edge(START, "research")
    g.add_conditional_edges(
        "research",
        route_after_research,
        {"research": "research", "memory_recall": "memory_recall"},
    )
    g.add_edge("memory_recall", "signal")
    g.add_edge("signal", "risk")
    g.add_edge("risk", "committee")
    g.add_conditional_edges(
        "committee",
        route_after_committee,
        {"execute": "execute", "end": END},
    )
    g.add_edge("execute", END)
    return g.compile()
