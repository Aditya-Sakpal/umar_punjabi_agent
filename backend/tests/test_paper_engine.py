"""Unit tests for PaperEngine (no network)."""
import pytest

from app.services.paper_engine import PaperEngine


class FakeBinance:
    async def price(self, symbol: str) -> dict:
        return {"symbol": symbol, "price": 100_000.0, "stale": False}


@pytest.mark.asyncio
async def test_simulate_hold_is_noop():
    engine = PaperEngine(FakeBinance())  # type: ignore[arg-type]
    order = await engine.simulate(
        decision={
            "action": "HOLD",
            "confidence": 0.3,
            "size_pct": 0.0,
            "stop_loss_pct": 0.0,
            "rationale": "wait",
        },
        symbol="BTCUSDT",
        run_id="t1",
    )
    assert order["filled"] is False
    assert order["qty"] == 0.0


@pytest.mark.asyncio
async def test_simulate_buy_computes_qty_from_equity():
    engine = PaperEngine(FakeBinance(), equity_usd=100_000.0)  # type: ignore[arg-type]
    order = await engine.simulate(
        decision={
            "action": "BUY",
            "confidence": 0.6,
            "size_pct": 2.5,
            "stop_loss_pct": 3.0,
            "rationale": "test",
        },
        symbol="BTCUSDT",
        run_id="t2",
    )
    assert order["filled"] is True
    assert order["notional_usd"] == 2500.0
    assert order["qty"] > 0
    assert order["price"] > 100_000.0  # slippage on buy
