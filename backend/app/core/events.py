"""WSEvent envelope — single source of truth for streaming (mirror in frontend)."""
from typing import Literal, TypedDict

EventType = Literal[
    "agent_status",
    "token",
    "evidence",
    "signal_ready",
    "risk_ready",
    "decision_ready",
    "order_filled",
    "error",
    "done",
]

EVENT_TYPES: tuple[EventType, ...] = (
    "agent_status",
    "token",
    "evidence",
    "signal_ready",
    "risk_ready",
    "decision_ready",
    "order_filled",
    "error",
    "done",
)

GRAPH_NODES = frozenset({"research", "signal", "risk", "committee", "execute"})

EVENT_VERSION = "1.0"


class EventDraft(TypedDict):
    """Translator output — ``seq`` and ``ts`` are added by EventBus at publish time."""

    run_id: str
    type: EventType
    payload: dict


class WSEvent(EventDraft, total=False):
    event_version: str
    seq: int
    ts: str
