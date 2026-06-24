"""Node degrade contract — no raises, safe defaults (mocked LLM/tools)."""
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.deps import NodeDeps
from app.agents.nodes import committee, execute, research, risk, signal
from app.services.paper_engine import PaperEngine
from tests.stubs import StubMemoryTool


class StubBinance:
    async def funding(self, symbol: str) -> dict:
        return {"funding_rate": 0.0001, "stale": False}

    async def ohlcv(self, symbol: str, interval: str = "1h", limit: int = 48) -> dict:
        return {
            "candles": [
                {"close": 100.0 + i, "high": 101.0, "low": 99.0} for i in range(10)
            ]
        }

    async def price(self, symbol: str) -> dict:
        return {"price": 100.0, "stale": False}


def _deps() -> NodeDeps:
    b = StubBinance()
    return NodeDeps(
        binance=b,  # type: ignore[arg-type]
        coingecko=b,  # type: ignore[arg-type]
        news=b,  # type: ignore[arg-type]
        onchain=b,  # type: ignore[arg-type]
        paper_engine=PaperEngine(b),  # type: ignore[arg-type]
        memory=StubMemoryTool(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_research_degrade_never_raises():
    deps = _deps()
    with patch("app.agents.nodes.research.structured_llm", AsyncMock(side_effect=RuntimeError("boom"))):
        out = await research.make_node(deps)({"symbol": "BTCUSDT", "trigger": "user"})
    assert out["status"] == "degraded:research"
    assert out["errors"]


@pytest.mark.asyncio
async def test_risk_degrade_never_raises():
    deps = _deps()

    class FailFunding:
        async def funding(self, symbol: str):
            raise OSError("down")

        async def ohlcv(self, *a, **kw):
            return await StubBinance().ohlcv("BTCUSDT")

    broken = NodeDeps(
        binance=FailFunding(),  # type: ignore[arg-type]
        coingecko=deps.coingecko,
        news=deps.news,
        onchain=deps.onchain,
        paper_engine=deps.paper_engine,
        memory=StubMemoryTool(),
    )
    state = {
        "symbol": "BTCUSDT",
        "signal": {"direction": "BUY", "confidence": 0.7, "thesis": "x", "horizon": "intraday"},
        "evidence": [],
    }
    out = await risk.make_node(broken)(state)
    assert out["status"] == "degraded:risk"
    assert out["risk"]["veto"] is False


@pytest.mark.asyncio
async def test_execute_hold_noop():
    deps = _deps()
    out = await execute.make_node(deps)(
        {
            "run_id": "r1",
            "symbol": "BTCUSDT",
            "decision": {
                "action": "HOLD",
                "confidence": 0.2,
                "size_pct": 0.0,
                "stop_loss_pct": 0.0,
                "rationale": "flat",
            },
        }
    )
    assert out["sim_order"]["filled"] is False
