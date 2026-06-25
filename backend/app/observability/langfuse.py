"""LangFuse callback handler factory (stub — full tracing in Task 20)."""
from __future__ import annotations

from langchain_core.callbacks.base import AsyncCallbackHandler


class _NoOpCallbackHandler(AsyncCallbackHandler):
    """LangChain-compatible no-op until LangFuse SDK is wired."""

    run_inline: bool = False


def langfuse_handler(
    run_id: str,
    symbol: str,
    trigger: str = "user",
) -> AsyncCallbackHandler:
    """Return a LangChain callback handler for this run, or a no-op stub."""
    # Full implementation deferred to observability phase; must subclass
    # AsyncCallbackHandler so LangGraph's astream_events callback manager works.
    del run_id, symbol, trigger
    return _NoOpCallbackHandler()
