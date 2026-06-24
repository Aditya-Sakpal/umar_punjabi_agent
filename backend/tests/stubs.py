"""Shared test stubs."""
from __future__ import annotations

from app.services.memory import format_historical_setups


class StubMemoryTool:
    def __init__(self, memories: list | None = None, *, fail: bool = False) -> None:
        self._memories = memories or []
        self._fail = fail
        self.stored: list[dict] = []

    async def recall(self, query: str, symbol: str, *, limit: int = 5) -> list:
        if self._fail:
            raise RuntimeError("memory down")
        return self._memories[:limit]

    async def recall_for_state(self, state, *, limit: int = 5) -> list:
        return await self.recall("", state.get("symbol", ""), limit=limit)

    def format_for_signal(self, memories: list) -> str:
        return format_historical_setups(memories)

    async def remember_run(self, state) -> str | None:
        self.stored.append(dict(state))
        return "stub-id"
