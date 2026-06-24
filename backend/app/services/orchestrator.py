"""Graph stream orchestrator — astream_events → translator → event bus."""
from __future__ import annotations

import logging
from typing import Any, Literal

from app.agents.state import AgentState
from app.core.events import GRAPH_NODES
from app.observability.langfuse import langfuse_handler
from app.services.event_bus import EventBus
from app.services.memory import MemoryRecallService
from app.services.translator import _chain_output, _node_name, translate

logger = logging.getLogger(__name__)

DoneStatus = Literal["completed", "failed"]


class GraphOrchestrator:
    """Runs the compiled graph with streaming and publishes translated WSEvents."""

    def __init__(
        self,
        graph: Any,
        event_bus: EventBus,
        memory: MemoryRecallService | None = None,
    ) -> None:
        self._graph = graph
        self._bus = event_bus
        self._memory = memory

    async def run(
        self,
        *,
        run_id: str,
        symbol: str,
        trigger: str = "user",
    ) -> None:
        """Stream one graph run; always ends with exactly one ``done`` event."""
        status: DoneStatus = "failed"
        initial: AgentState = {
            "run_id": run_id,
            "symbol": symbol.upper(),
            "trigger": trigger,  # type: ignore[typeddict-item]
            "revision_count": 0,
        }
        final_state: dict = dict(initial)
        config = {
            "configurable": {"thread_id": run_id},
            "metadata": {"run_id": run_id, "symbol": symbol.upper(), "trigger": trigger},
            "tags": ["deepchain"],
            "callbacks": [langfuse_handler(run_id, symbol.upper(), trigger)],
        }

        try:
            async for ev in self._graph.astream_events(
                initial,
                version="v2",
                config=config,
            ):
                if ev.get("event") == "on_chain_end":
                    node = _node_name(ev)
                    if node in GRAPH_NODES:
                        final_state.update(_chain_output(ev))
                draft = translate(ev, run_id)
                if draft:
                    await self._bus.publish(
                        run_id,
                        {"type": draft["type"], "payload": draft["payload"]},
                    )
            status = "completed"
            if self._memory:
                try:
                    await self._memory.store_from_run(final_state)  # type: ignore[arg-type]
                except Exception:
                    logger.exception("memory persist failed run_id=%s", run_id)
        except Exception as exc:
            logger.exception("graph run failed run_id=%s", run_id)
            await self._bus.publish(
                run_id,
                {
                    "type": "error",
                    "payload": {"agent": "graph", "message": str(exc)},
                },
            )
        finally:
            await self._bus.publish(
                run_id,
                {"type": "done", "payload": {"status": status}},
            )
