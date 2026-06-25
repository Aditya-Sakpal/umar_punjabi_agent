import { describe, expect, it } from "vitest";
import { applyEventToState, initialRunState } from "../store/runStore.logic";
import type { WSEvent } from "../types/events";

describe("runStore applyEvent", () => {
  it("appends token deltas per agent", () => {
    let state = initialRunState();
    const token: WSEvent = {
      run_id: "r1",
      seq: 1,
      type: "token",
      payload: { agent: "risk", delta: "Funding elevated" },
    };
    state = applyEventToState(state, token);
    expect(state.agents.risk.tokens).toBe("Funding elevated");
  });

  it("updates agent_status to challenging for risk", () => {
    let state = initialRunState();
    state = applyEventToState(state, {
      run_id: "r1",
      type: "agent_status",
      payload: { agent: "risk", state: "challenging" },
    });
    expect(state.agents.risk.status).toBe("challenging");
  });

  it("collects evidence and updates market snapshot", () => {
    let state = initialRunState();
    state = applyEventToState(state, {
      run_id: "r1",
      type: "evidence",
      payload: { source: "binance", claim: "funding rate", value: "0.012%" },
    });
    expect(state.evidence).toHaveLength(1);
    expect(state.market.funding).toBe("0.012%");
  });

  it("sets decision on decision_ready", () => {
    let state = initialRunState();
    state = applyEventToState(state, {
      run_id: "r1",
      type: "decision_ready",
      payload: {
        action: "BUY",
        confidence: 0.55,
        size_pct: 2,
        stop_loss_pct: 3,
        rationale: "Sized entry",
      },
    });
    expect(state.decision?.action).toBe("BUY");
    expect(state.agents.committee.status).toBe("done");
  });

  it("marks run completed on done", () => {
    let state = initialRunState();
    state = applyEventToState(state, {
      run_id: "r1",
      type: "done",
      payload: { status: "completed" },
    });
    expect(state.runStatus).toBe("completed");
  });
});
