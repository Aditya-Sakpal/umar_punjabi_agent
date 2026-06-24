"""LangFuse callback handler factory (stub — full tracing in Task 20)."""
from __future__ import annotations

from typing import Any


class _NoOpCallbackHandler:
    """Placeholder until LangFuse SDK is wired with settings."""

    def __init__(self, **_: Any) -> None:
        pass


def langfuse_handler(
    run_id: str,
    symbol: str,
    trigger: str = "user",
) -> Any:
    """Return a LangChain callback handler for this run, or a no-op stub."""
    # Full implementation deferred to observability phase; orchestrator always
    # receives a list-shaped callbacks slot for future LangFuse wiring.
    return _NoOpCallbackHandler(run_id=run_id, symbol=symbol, trigger=trigger)
