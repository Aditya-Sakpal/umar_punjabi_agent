"""Memory recall node — advisory retrieval between Research and Signal."""
from __future__ import annotations

from app.agents.deps import NodeDeps
from app.agents.state import AgentState, SimilarMemory

OWNED_KEYS = frozenset({"similar_memories", "status", "errors"})


def make_node(deps: NodeDeps):
    async def memory_recall_node(state: AgentState) -> dict:
        try:
            memories: list[SimilarMemory] = await deps.memory.recall_for_state(state, limit=5)
            return {"similar_memories": memories, "status": "memory_recall_done"}
        except Exception as e:
            return {
                "similar_memories": [],
                "errors": [f"memory_recall: {e}"],
                "status": "degraded:memory_recall",
            }

    return memory_recall_node
