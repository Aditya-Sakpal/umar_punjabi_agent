"""Committee node — reconciles signal + risk into a final decision."""
from __future__ import annotations

from app.agents.deps import NodeDeps
from app.agents.llm import structured_llm
from app.agents.nodes._helpers import hold_decision, json_dumps
from app.agents.prompts.committee import COMMITTEE_SYSTEM, COMMITTEE_USER
from app.agents.state import AgentState, Decision

OWNED_KEYS = frozenset({"decision", "status", "errors"})


def make_node(deps: NodeDeps):
    del deps

    async def committee_node(state: AgentState) -> dict:
        try:
            risk = state.get("risk", {})
            if risk.get("veto"):
                return {
                    "decision": hold_decision(
                        rationale="Risk veto — trade rejected; standing aside per risk policy."
                    ),
                    "status": "committee_done",
                }

            user = COMMITTEE_USER.format(
                signal=json_dumps(state.get("signal", {})),
                risk=json_dumps(risk),
                evidence=json_dumps(state.get("evidence", [])),
            )
            result: Decision = await structured_llm(
                system=COMMITTEE_SYSTEM,
                user=user,
                schema=Decision,
                tags=["agent:committee"],
                tier="strong",
                max_tokens=1024,
            )
            # Hard respect veto if model ignored it
            if risk.get("veto") and result["action"] != "HOLD":
                result = hold_decision(
                    rationale="Risk veto overridden model output — forced HOLD."
                )
            return {"decision": result, "status": "committee_done"}
        except Exception as e:
            return {
                "errors": [f"committee: {e}"],
                "status": "degraded:committee",
                "decision": hold_decision(),
            }

    return committee_node
