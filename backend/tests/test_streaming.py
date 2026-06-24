"""Streaming pipeline tests — orchestrator, WebSocket, concurrent runs."""
from __future__ import annotations

import asyncio
import threading
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_orchestrator
from app.api.routes.analyze import router as analyze_router
from app.api.routes.ws import router as ws_router
from app.core.events import EVENT_VERSION
from app.services.event_bus import EventBus
from app.services.orchestrator import GraphOrchestrator


def _chunk(text: str):
    return SimpleNamespace(content=text)


SCRIPTED_GRAPH_EVENTS: list[dict[str, Any]] = [
    {"event": "on_chain_start", "name": "research", "data": {}},
    {
        "event": "on_chat_model_stream",
        "tags": ["agent:research"],
        "data": {"chunk": _chunk("Scanning...")},
    },
    {
        "event": "on_tool_end",
        "data": {"output": {"source": "binance", "claim": "funding rate", "value": "0.05%"}},
    },
    {"event": "on_chain_start", "name": "signal", "data": {}},
    {
        "event": "on_chat_model_stream",
        "tags": ["agent:signal"],
        "data": {"chunk": _chunk("Bull case.")},
    },
    {
        "event": "on_chain_end",
        "name": "signal",
        "data": {
            "output": {
                "signal": {
                    "direction": "BUY",
                    "confidence": 0.6,
                    "thesis": "breakout",
                    "horizon": "swing",
                }
            }
        },
    },
    {"event": "on_chain_start", "name": "risk", "data": {}},
    {
        "event": "on_chat_model_stream",
        "tags": ["agent:risk"],
        "data": {"chunk": _chunk("Funding elevated.")},
    },
    {
        "event": "on_chain_end",
        "name": "risk",
        "data": {
            "output": {
                "risk": {
                    "concerns": ["crowded"],
                    "adjusted_confidence": 0.4,
                    "suggested_size_pct": 2.0,
                    "stop_loss_pct": 3.0,
                    "veto": False,
                }
            }
        },
    },
    {"event": "on_chain_start", "name": "committee", "data": {}},
    {
        "event": "on_chain_end",
        "name": "committee",
        "data": {
            "output": {
                "decision": {
                    "action": "BUY",
                    "confidence": 0.5,
                    "size_pct": 2.0,
                    "stop_loss_pct": 3.0,
                    "rationale": "Go.",
                }
            }
        },
    },
]


class ScriptedGraph:
    def __init__(
        self,
        events: list[dict[str, Any]] | None = None,
        *,
        delay: float = 0.0,
        fail: bool = False,
    ) -> None:
        self._events = events if events is not None else SCRIPTED_GRAPH_EVENTS
        self._delay = delay
        self._fail = fail

    async def astream_events(self, state: dict, version: str = "v2", config: dict | None = None):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail:
            raise RuntimeError("graph exploded")
        for ev in self._events:
            yield ev


def _build_streaming_app(graph: ScriptedGraph) -> FastAPI:
    app = FastAPI()
    bus = EventBus(FakeRedis(decode_responses=True))
    orchestrator = GraphOrchestrator(graph, bus)
    app.state.event_bus = bus
    app.state.orchestrator = orchestrator
    app.include_router(analyze_router)
    app.include_router(ws_router)
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    return app


def _run_orchestrator_in_thread(orchestrator: GraphOrchestrator, run_id: str, symbol: str) -> threading.Thread:
    """Starlette TestClient blocks the loop — run the async orchestrator on a side thread."""

    def _target() -> None:
        asyncio.run(orchestrator.run(run_id=run_id, symbol=symbol))

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    return thread


@pytest.mark.asyncio
async def test_orchestrator_publishes_translated_sequence():
    bus = EventBus(FakeRedis(decode_responses=True))
    orch = GraphOrchestrator(ScriptedGraph(delay=0), bus)
    run_id = "orch-seq"

    async def drain() -> list[dict]:
        out: list[dict] = []
        async for ev in bus.subscribe(run_id):
            out.append(ev)
        return out

    task = asyncio.create_task(drain())
    await asyncio.sleep(0.05)
    await orch.run(run_id=run_id, symbol="BTCUSDT")
    received = await asyncio.wait_for(task, timeout=5)

    types = [e["type"] for e in received]
    assert types == [
        "agent_status",
        "token",
        "evidence",
        "agent_status",
        "token",
        "signal_ready",
        "agent_status",
        "token",
        "risk_ready",
        "agent_status",
        "decision_ready",
        "done",
    ]
    assert received[-1]["payload"]["status"] == "completed"
    assert all(e.get("event_version") == EVENT_VERSION for e in received)
    assert [e["seq"] for e in received] == list(range(1, len(received) + 1))


@pytest.mark.asyncio
async def test_orchestrator_failure_publishes_error_and_done():
    bus = EventBus(FakeRedis(decode_responses=True))
    orch = GraphOrchestrator(ScriptedGraph(fail=True), bus)
    run_id = "orch-fail"

    async def drain() -> list[dict]:
        out: list[dict] = []
        async for ev in bus.subscribe(run_id):
            out.append(ev)
        return out

    task = asyncio.create_task(drain())
    await asyncio.sleep(0.05)
    await orch.run(run_id=run_id, symbol="BTCUSDT")
    received = await asyncio.wait_for(task, timeout=5)

    assert [e["type"] for e in received] == ["error", "done"]
    assert received[0]["payload"]["agent"] == "graph"
    assert received[1]["payload"]["status"] == "failed"


def test_analyze_stream_returns_run_id():
    app = _build_streaming_app(ScriptedGraph(delay=0.3))
    client = TestClient(app)
    r = client.post("/analyze/stream", json={"symbol": "BTCUSDT"})
    assert r.status_code == 200
    assert "run_id" in r.json()


def test_ws_streaming_sequence_e2e():
    app = _build_streaming_app(ScriptedGraph(delay=0))
    client = TestClient(app)
    run_id = str(uuid.uuid4())
    orch: GraphOrchestrator = app.state.orchestrator

    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        thread = _run_orchestrator_in_thread(orch, run_id, "BTCUSDT")
        events: list[dict] = []
        while True:
            events.append(ws.receive_json())
            if events[-1]["type"] == "done":
                break
        thread.join(timeout=5)

    assert events[0]["type"] == "agent_status"
    assert events[0]["payload"]["agent"] == "research"
    tokens = [e for e in events if e["type"] == "token"]
    assert {t["payload"]["agent"] for t in tokens} == {"research", "signal", "risk"}
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["payload"]["status"] == "completed"
    assert all(e["run_id"] == run_id for e in events)


@pytest.mark.asyncio
async def test_concurrent_orchestrator_runs_on_shared_bus():
    bus = EventBus(FakeRedis(decode_responses=True))
    orch = GraphOrchestrator(ScriptedGraph(delay=0), bus)

    async def drain(run_id: str) -> list[dict]:
        out: list[dict] = []
        async for ev in bus.subscribe(run_id):
            out.append(ev)
        return out

    t_a = asyncio.create_task(drain("run-a"))
    t_b = asyncio.create_task(drain("run-b"))
    await asyncio.sleep(0.05)
    await asyncio.gather(
        orch.run(run_id="run-a", symbol="BTCUSDT"),
        orch.run(run_id="run-b", symbol="ETHUSDT"),
    )
    a, b = await asyncio.gather(t_a, t_b)
    assert a[0]["run_id"] == "run-a" and b[0]["run_id"] == "run-b"
    assert a[0]["seq"] == 1 and b[0]["seq"] == 1


def test_failure_path_over_websocket():
    app = _build_streaming_app(ScriptedGraph(delay=0, fail=True))
    client = TestClient(app)
    run_id = str(uuid.uuid4())
    orch: GraphOrchestrator = app.state.orchestrator

    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        thread = _run_orchestrator_in_thread(orch, run_id, "BTCUSDT")
        events: list[dict] = []
        while True:
            events.append(ws.receive_json())
            if events[-1]["type"] == "done":
                break
        thread.join(timeout=5)

    assert [e["type"] for e in events] == ["error", "done"]
    assert events[-1]["payload"]["status"] == "failed"


def test_invalid_symbol_on_stream_returns_422():
    app = _build_streaming_app(ScriptedGraph())
    client = TestClient(app)
    r = client.post("/analyze/stream", json={"symbol": "DOGEUSDT"})
    assert r.status_code == 422
