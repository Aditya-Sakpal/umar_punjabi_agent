/** Mirror of backend `app/core/events.py` */
export type EventType =
  | "agent_status"
  | "token"
  | "evidence"
  | "signal_ready"
  | "risk_ready"
  | "decision_ready"
  | "order_filled"
  | "error"
  | "done";

export type AgentName = "research" | "signal" | "risk" | "committee" | "execute";

export type AgentUiState =
  | "idle"
  | "thinking"
  | "challenging"
  | "deciding"
  | "done"
  | "error";

export interface WSEvent {
  event_version?: string;
  run_id: string;
  seq?: number;
  type: EventType;
  payload: Record<string, unknown>;
  ts?: string;
}

export interface EvidenceItem {
  source: string;
  claim: string;
  value: string | number | null;
}

export interface SignalPayload {
  direction: "BUY" | "SELL" | "HOLD";
  confidence: number;
  thesis: string;
  horizon: string;
}

export interface RiskPayload {
  concerns: string[];
  adjusted_confidence: number;
  suggested_size_pct: number;
  stop_loss_pct: number;
  veto: boolean;
}

export interface DecisionPayload {
  action: "BUY" | "SELL" | "HOLD";
  confidence: number;
  size_pct: number;
  stop_loss_pct: number;
  rationale: string;
}

export interface OrderPayload {
  symbol?: string;
  side?: string;
  qty?: number;
  price?: number;
  pnl?: number;
}

export type RunStatus = "idle" | "connecting" | "running" | "completed" | "failed";

export interface PositionRow {
  id: string;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  pnl: number;
  ts: string;
}
