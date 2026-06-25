/** Pure event reducer extracted for unit tests. */
import type {
  AgentName,
  AgentUiState,
  DecisionPayload,
  EvidenceItem,
  OrderPayload,
  PositionRow,
  RiskPayload,
  RunStatus,
  SignalPayload,
  WSEvent,
} from "../types/events";

export interface AgentSlice {
  status: AgentUiState;
  tokens: string;
}

export interface MarketSnapshot {
  price: string;
  funding: string;
  volume: string;
  sentiment: string;
}

export interface RunStoreState {
  symbol: string;
  runId: string | null;
  runStatus: RunStatus;
  agents: Record<AgentName, AgentSlice>;
  evidence: EvidenceItem[];
  signal: SignalPayload | null;
  risk: RiskPayload | null;
  decision: DecisionPayload | null;
  lastOrder: OrderPayload | null;
  positions: PositionRow[];
  errors: string[];
  lastSeq: number;
}

export const AGENT_ORDER: AgentName[] = ["research", "signal", "risk", "committee"];

const idleAgents = (): Record<AgentName, AgentSlice> => ({
  research: { status: "idle", tokens: "" },
  signal: { status: "idle", tokens: "" },
  risk: { status: "idle", tokens: "" },
  committee: { status: "idle", tokens: "" },
  execute: { status: "idle", tokens: "" },
});

export const initialRunState = (): RunStoreState & { market: MarketSnapshot } => ({
  symbol: "BTCUSDT",
  runId: null,
  runStatus: "idle",
  agents: idleAgents(),
  evidence: [],
  signal: null,
  risk: null,
  decision: null,
  lastOrder: null,
  positions: [],
  errors: [],
  lastSeq: 0,
  market: { price: "—", funding: "—", volume: "—", sentiment: "Neutral" },
});

function mapAgentState(state: string): AgentUiState {
  if (state === "challenging") return "challenging";
  if (state === "deciding") return "deciding";
  return "thinking";
}

function evidenceFromPayload(payload: Record<string, unknown>): EvidenceItem {
  return {
    source: String(payload.source ?? "unknown"),
    claim: String(payload.claim ?? ""),
    value: (payload.value as string | number | null) ?? null,
  };
}

function updateMarketFromEvidence(snapshot: MarketSnapshot, item: EvidenceItem): MarketSnapshot {
  const next = { ...snapshot };
  const claim = item.claim.toLowerCase();
  if (claim.includes("price")) next.price = String(item.value ?? next.price);
  if (claim.includes("funding")) next.funding = String(item.value ?? next.funding);
  if (claim.includes("volume")) next.volume = String(item.value ?? next.volume);
  return next;
}

export function applyEventToState(
  state: RunStoreState & { market: MarketSnapshot },
  event: WSEvent,
): RunStoreState & { market: MarketSnapshot } {
  const next = { ...state, agents: { ...state.agents }, evidence: [...state.evidence], errors: [...state.errors], positions: [...state.positions] };
  if (event.seq != null) next.lastSeq = event.seq;

  switch (event.type) {
    case "agent_status": {
      const agent = event.payload.agent as AgentName;
      const ui = mapAgentState(String(event.payload.state ?? "thinking"));
      if (next.agents[agent]) next.agents[agent] = { ...next.agents[agent], status: ui };
      break;
    }
    case "token": {
      const agent = event.payload.agent as AgentName;
      const delta = String(event.payload.delta ?? "");
      if (next.agents[agent]) {
        next.agents[agent] = {
          status: next.agents[agent].status === "idle" ? "thinking" : next.agents[agent].status,
          tokens: next.agents[agent].tokens + delta,
        };
      }
      break;
    }
    case "evidence": {
      const item = evidenceFromPayload(event.payload);
      next.evidence.push(item);
      next.market = updateMarketFromEvidence(next.market, item);
      break;
    }
    case "signal_ready":
      next.signal = event.payload as unknown as SignalPayload;
      next.agents.signal = { ...next.agents.signal, status: "done" };
      break;
    case "risk_ready":
      next.risk = event.payload as unknown as RiskPayload;
      next.agents.risk = { ...next.agents.risk, status: "done" };
      break;
    case "decision_ready":
      next.decision = event.payload as unknown as DecisionPayload;
      next.agents.committee = { ...next.agents.committee, status: "done" };
      break;
    case "order_filled": {
      const order = event.payload as unknown as OrderPayload;
      next.lastOrder = order;
      next.agents.execute = { ...next.agents.execute, status: "done" };
      next.positions.unshift({
        id: `${event.run_id}-${event.seq ?? next.positions.length}`,
        symbol: String(order.symbol ?? next.symbol),
        side: String(order.side ?? "BUY"),
        qty: Number(order.qty ?? 0),
        price: Number(order.price ?? 0),
        pnl: Number(order.pnl ?? 0),
        ts: event.ts ?? new Date().toISOString(),
      });
      break;
    }
    case "error":
      next.errors.push(`${event.payload.agent}: ${event.payload.message}`);
      break;
    case "done":
      next.runStatus = (event.payload.status === "failed" ? "failed" : "completed") as RunStatus;
      break;
  }
  return next;
}

export function agentLabel(name: AgentName): string {
  const labels: Record<AgentName, string> = {
    research: "Research Agent",
    signal: "Signal Agent",
    risk: "Risk Agent",
    committee: "Committee",
    execute: "Execute",
  };
  return labels[name];
}

export function agentStatusLabel(status: AgentUiState): string {
  const map: Record<AgentUiState, string> = {
    idle: "Idle",
    thinking: "Thinking...",
    challenging: "Challenging...",
    deciding: "Deciding...",
    done: "Done",
    error: "Error",
  };
  return map[status];
}
