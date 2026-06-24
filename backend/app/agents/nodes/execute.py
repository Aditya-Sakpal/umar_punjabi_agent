"""Execute node — deterministic paper fill at live Binance price (no LLM)."""
from __future__ import annotations

from app.agents.deps import NodeDeps
from app.agents.nodes._helpers import hold_decision
from app.agents.state import AgentState

OWNED_KEYS = frozenset({"sim_order", "status", "errors"})


def make_node(deps: NodeDeps):
    async def execute_node(state: AgentState) -> dict:
        try:
            decision = state.get("decision") or hold_decision()
            run_id = state.get("run_id", "unknown")
            symbol = state["symbol"]
            sim_order = await deps.paper_engine.simulate(
                decision=decision, symbol=symbol, run_id=run_id
            )
            return {"sim_order": sim_order, "status": "execute_done"}
        except Exception as e:
            return {
                "errors": [f"execute: {e}"],
                "status": "degraded:execute",
                "sim_order": {
                    "run_id": state.get("run_id", "unknown"),
                    "symbol": state.get("symbol", ""),
                    "action": "HOLD",
                    "filled": False,
                    "qty": 0.0,
                    "price": None,
                    "fee": 0.0,
                    "error": str(e),
                },
            }

    return execute_node
