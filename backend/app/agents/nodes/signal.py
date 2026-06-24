"""Signal node — directional thesis from research brief + evidence."""
from __future__ import annotations

from app.agents.deps import NodeDeps
from app.agents.llm import structured_llm
from app.agents.nodes._helpers import hold_signal, json_dumps
from app.agents.prompts.signal import SIGNAL_SYSTEM, SIGNAL_USER
from app.agents.state import AgentState, Signal

OWNED_KEYS = frozenset({"signal", "status", "errors"})


def make_node(deps: NodeDeps):
    async def signal_node(state: AgentState) -> dict:
        try:
            memories = state.get("similar_memories") or []
            historical = deps.memory.format_for_signal(memories)
            user = SIGNAL_USER.format(
                research_brief=state.get("research_brief", ""),
                evidence=json_dumps(state.get("evidence", [])),
                historical_setups=historical,
            )
            result: Signal = await structured_llm(
                system=SIGNAL_SYSTEM,
                user=user,
                schema=Signal,
                tags=["agent:signal"],
                tier="strong",
                max_tokens=1024,
            )
            return {"signal": result, "status": "signal_done"}
        except Exception as e:
            return {
                "errors": [f"signal: {e}"],
                "status": "degraded:signal",
                "signal": hold_signal(),
            }

    return signal_node
