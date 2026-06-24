"""Memory tool — thin facade over :class:`MemoryRecallService`."""
from __future__ import annotations

from app.agents.state import AgentState
from app.services.memory import (
    MemoryRecallService,
    SimilarMemory,
    build_recall_query,
    format_historical_setups,
)


class MemoryTool:
    def __init__(self, service: MemoryRecallService) -> None:
        self._service = service

    async def recall(self, query: str, symbol: str, *, limit: int = 5) -> list[SimilarMemory]:
        return await self._service.recall(query, symbol, limit=limit)

    async def recall_for_state(self, state: AgentState, *, limit: int = 5) -> list[SimilarMemory]:
        return await self.recall(build_recall_query(state), state["symbol"], limit=limit)

    def format_for_signal(self, memories: list[SimilarMemory]) -> str:
        return format_historical_setups(memories)

    async def remember_run(self, state: AgentState) -> str | None:
        return await self._service.store_from_run(state)
