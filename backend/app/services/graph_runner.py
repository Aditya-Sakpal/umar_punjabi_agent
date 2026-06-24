"""Synchronous graph execution for Task 9 (streaming orchestrator arrives in Task 12)."""
from __future__ import annotations

from typing import Any

from app.agents.state import AgentState


class GraphRunner:
    """Runs the compiled LangGraph to completion and returns final state."""

    def __init__(self, graph: Any) -> None:
        self._graph = graph

    async def run(
        self,
        *,
        run_id: str,
        symbol: str,
        trigger: str = "user",
    ) -> AgentState:
        initial: AgentState = {
            "run_id": run_id,
            "symbol": symbol.upper(),
            "trigger": trigger,  # type: ignore[typeddict-item]
            "revision_count": 0,
        }
        result = await self._graph.ainvoke(initial)
        return result  # type: ignore[return-value]
