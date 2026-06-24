"""Risk node — adversarial review; pulls funding/vol, appends funding evidence."""
from __future__ import annotations

from app.agents.deps import NodeDeps
from app.agents.llm import structured_llm
from app.agents.nodes._helpers import (
    conservative_risk,
    evidence_item,
    format_volatility,
    json_dumps,
)
from app.agents.prompts.risk import RISK_SYSTEM, RISK_USER
from app.agents.state import AgentState, RiskAssessment

OWNED_KEYS = frozenset({"risk", "evidence", "status", "errors"})


def make_node(deps: NodeDeps):
    async def risk_node(state: AgentState) -> dict:
        symbol = state["symbol"]
        try:
            funding_data = await deps.binance.funding(symbol)
            funding_rate = float(funding_data["funding_rate"])
            funding_str = f"{funding_rate * 100:.4f}%"

            ohlcv = await deps.binance.ohlcv(symbol, interval="1h", limit=48)
            vol_str = format_volatility(ohlcv)

            portfolio = deps.paper_engine.snapshot()

            user = RISK_USER.format(
                signal=json_dumps(state.get("signal", {})),
                evidence=json_dumps(state.get("evidence", [])),
                funding=funding_str,
                vol=vol_str,
                portfolio=json_dumps(portfolio),
            )
            result: RiskAssessment = await structured_llm(
                system=RISK_SYSTEM,
                user=user,
                schema=RiskAssessment,
                tags=["agent:risk"],
                tier="strong",
                max_tokens=1536,
            )
            funding_ev = evidence_item(
                "binance",
                "funding rate (risk review)",
                funding_str,
                stale=bool(funding_data.get("stale")),
            )
            return {
                "risk": result,
                "evidence": [funding_ev],
                "status": "risk_done",
            }
        except Exception as e:
            return {
                "errors": [f"risk: {e}"],
                "status": "degraded:risk",
                "risk": conservative_risk(),
                "evidence": [],
            }

    return risk_node
