"""Tests for POST /analyze (mocked graph — no live LLM)."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.graph import graph_info
from app.api.deps import get_graph_runner
from app.api.routes.analyze import router as analyze_router
from app.services.graph_runner import GraphRunner


class MockGraphRunner(GraphRunner):
    def __init__(self, final_state: dict[str, Any]) -> None:
        self._final_state = final_state

    async def run(self, *, run_id: str, symbol: str, trigger: str = "user") -> dict:
        return {**self._final_state, "run_id": run_id, "symbol": symbol}


HOLD_STATE = {
    "decision": {
        "action": "HOLD",
        "confidence": 0.4,
        "size_pct": 0.0,
        "stop_loss_pct": 0.0,
        "rationale": "No edge.",
    },
}

BUY_STATE = {
    "decision": {
        "action": "BUY",
        "confidence": 0.55,
        "size_pct": 2.0,
        "stop_loss_pct": 2.5,
        "rationale": "Go long.",
    },
    "sim_order": {
        "run_id": "placeholder",
        "symbol": "BTCUSDT",
        "action": "BUY",
        "side": "BUY",
        "filled": True,
        "qty": 0.01,
        "price": 62000.0,
        "fee": 1.2,
        "notional_usd": 2000.0,
        "stop_loss_pct": 2.5,
    },
}


@pytest.fixture
def api_client():
    def _build(state: dict[str, Any]) -> TestClient:
        test_app = FastAPI()
        test_app.include_router(analyze_router)
        runner = MockGraphRunner(state)
        test_app.dependency_overrides[get_graph_runner] = lambda: runner
        return TestClient(test_app)

    return _build


def test_graph_info_exposes_topology():
    info = graph_info()
    assert "research" in info["nodes"]
    assert info["conditional_edges"]
    assert "route_after_research" in info["routing"]


def test_analyze_hold_path(api_client):
    client = api_client(HOLD_STATE)
    r = client.post("/analyze", json={"symbol": "BTCUSDT"})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"]["action"] == "HOLD"
    assert body.get("sim_order") is None
    assert "run_id" in body
    assert body["metadata"]["status"] == "completed"
    assert body["metadata"]["duration_ms"] >= 0


def test_analyze_buy_path_includes_sim_order(api_client):
    client = api_client(BUY_STATE)
    r = client.post("/analyze", json={"symbol": "ETHUSDT"})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"]["action"] == "BUY"
    assert body["sim_order"]["filled"] is True
    assert body["sim_order"]["qty"] > 0


def test_invalid_symbol_returns_422(api_client):
    client = api_client(HOLD_STATE)
    r = client.post("/analyze", json={"symbol": "DOGEUSDT"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "invalid_symbol"


def test_graph_failure_returns_structured_500(api_client):
    class FailingRunner(GraphRunner):
        def __init__(self) -> None:
            pass

        async def run(self, **kwargs):
            raise RuntimeError("boom")

    test_app = FastAPI()
    test_app.include_router(analyze_router)
    test_app.dependency_overrides[get_graph_runner] = lambda: FailingRunner()
    client = TestClient(test_app)
    r = client.post("/analyze", json={"symbol": "BTCUSDT"})
    assert r.status_code == 500
    assert r.json()["detail"]["code"] == "graph_execution_failed"


def test_openapi_includes_analyze():
    from app.main import create_app

    client = TestClient(create_app())
    schema = client.get("/openapi.json").json()
    assert "/analyze" in schema["paths"]
    assert "post" in schema["paths"]["/analyze"]
