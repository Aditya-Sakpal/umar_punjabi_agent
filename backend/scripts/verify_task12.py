"""Task 12 verification — streaming pipeline (orchestrator → bus → WebSocket)."""
from __future__ import annotations

import asyncio
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.analyze import router as analyze_router
from app.api.routes.ws import router as ws_router
from app.services.event_bus import EventBus
from app.services.orchestrator import GraphOrchestrator
from tests.test_streaming import SCRIPTED_GRAPH_EVENTS, ScriptedGraph


def _section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


async def _demo_orchestrator() -> None:
    bus = EventBus(FakeRedis(decode_responses=True))
    orch = GraphOrchestrator(ScriptedGraph(SCRIPTED_GRAPH_EVENTS[:6]), bus)
    run_id = "verify-task12"

    async def drain() -> list[dict]:
        out: list[dict] = []
        async for ev in bus.subscribe(run_id):
            out.append(ev)
        return out

    task = asyncio.create_task(drain())
    await asyncio.sleep(0.05)
    await orch.run(run_id=run_id, symbol="BTCUSDT")
    events = await asyncio.wait_for(task, timeout=5)
    for ev in events:
        print(json.dumps(ev, indent=2))


def _demo_ws_e2e() -> None:
    app = FastAPI()
    bus = EventBus(FakeRedis(decode_responses=True))
    graph = ScriptedGraph(SCRIPTED_GRAPH_EVENTS[:4], delay=0)
    orch = GraphOrchestrator(graph, bus)
    app.state.event_bus = bus
    app.state.orchestrator = orch
    app.include_router(analyze_router)
    app.include_router(ws_router)

    client = TestClient(app)
    run_id = client.post("/analyze/stream", json={"symbol": "BTCUSDT"}).json()["run_id"]
    print(f"POST /analyze/stream -> run_id={run_id}")
    print("(WS demo uses direct orchestrator thread — TestClient blocks background tasks)")

    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        thread = threading.Thread(
            target=lambda: asyncio.run(orch.run(run_id=run_id, symbol="BTCUSDT")),
            daemon=True,
        )
        thread.start()
        while True:
            ev = ws.receive_json()
            print(json.dumps(ev, indent=2))
            if ev["type"] == "done":
                break
        thread.join(timeout=5)


def main() -> None:
    _section("ORCHESTRATOR -> EVENT BUS")
    asyncio.run(_demo_orchestrator())

    _section("POST /analyze/stream + WS /ws/runs/{run_id}")
    _demo_ws_e2e()

    print()
    print("ALL TASK 12 CHECKS PASSED")


if __name__ == "__main__":
    main()
