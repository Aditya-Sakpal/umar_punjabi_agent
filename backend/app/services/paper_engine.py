"""Minimal paper trade simulator — live Binance price + simple slippage/fee.

Full position/PnL tracking arrives in Task 15; this task only needs a real fill
at the current market with qty derived from decision.size_pct × configured equity.
"""
from __future__ import annotations

from app.agents.state import Decision
from app.config import settings
from app.tools.binance import BinanceTool

SLIPPAGE_BPS = 5.0   # 5 bps against the trader
FEE_BPS = 10.0       # 10 bps taker fee


class PaperEngine:
    def __init__(self, binance: BinanceTool, *, equity_usd: float | None = None) -> None:
        self._binance = binance
        self.equity_usd = equity_usd if equity_usd is not None else settings.paper_equity_usd

    def snapshot(self) -> dict:
        """Portfolio stub for Risk node inputs (Task 15 adds real positions)."""
        return {
            "equity_usd": self.equity_usd,
            "positions": [],
            "exposure_pct": 0.0,
            "open_positions": 0,
        }

    async def simulate(self, *, decision: Decision, symbol: str, run_id: str) -> dict:
        action = decision["action"]
        if action == "HOLD":
            return {
                "run_id": run_id,
                "symbol": symbol,
                "action": "HOLD",
                "filled": False,
                "qty": 0.0,
                "price": None,
                "fee": 0.0,
                "notional_usd": 0.0,
                "stop_loss_pct": decision.get("stop_loss_pct", 0.0),
            }

        price_data = await self._binance.price(symbol)
        mid = float(price_data["price"])
        slip = SLIPPAGE_BPS / 10_000
        fill_price = mid * (1 + slip) if action == "BUY" else mid * (1 - slip)

        notional = self.equity_usd * (float(decision["size_pct"]) / 100.0)
        qty = notional / fill_price if fill_price > 0 else 0.0
        fee = notional * (FEE_BPS / 10_000)

        return {
            "run_id": run_id,
            "symbol": symbol,
            "action": action,
            "side": action,
            "filled": True,
            "qty": round(qty, 8),
            "price": round(fill_price, 2),
            "mid_price": round(mid, 2),
            "fee": round(fee, 4),
            "notional_usd": round(notional, 2),
            "stop_loss_pct": decision["stop_loss_pct"],
            "stale_price": bool(price_data.get("stale", False)),
        }
