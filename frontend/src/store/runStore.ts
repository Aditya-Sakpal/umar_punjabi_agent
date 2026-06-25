import type { WSEvent } from "../types/events";
import {
  agentLabel,
  agentStatusLabel,
  AGENT_ORDER,
  applyEventToState,
  initialRunState,
  type AgentSlice,
  type MarketSnapshot,
} from "./runStore.logic";

export type { AgentSlice, MarketSnapshot };
export { AGENT_ORDER, agentLabel, agentStatusLabel, initialRunState };

export interface RunStoreState {
  symbol: string;
  runId: string | null;
  runStatus: import("../types/events").RunStatus;
  agents: Record<import("../types/events").AgentName, AgentSlice>;
  evidence: import("../types/events").EvidenceItem[];
  signal: import("../types/events").SignalPayload | null;
  risk: import("../types/events").RiskPayload | null;
  decision: import("../types/events").DecisionPayload | null;
  lastOrder: import("../types/events").OrderPayload | null;
  positions: import("../types/events").PositionRow[];
  errors: string[];
  lastSeq: number;
}

export interface RunStore extends RunStoreState {
  market: MarketSnapshot;
  ws: WebSocket | null;
  setSymbol: (symbol: string) => void;
  resetRun: () => void;
  applyEvent: (event: WSEvent) => void;
  setRunMeta: (runId: string | null, status: import("../types/events").RunStatus) => void;
  setWebSocket: (ws: WebSocket | null) => void;
  startAnalysis: () => Promise<void>;
}

type SetState = {
  (partial: Partial<RunStore>): void;
  (fn: (state: RunStore) => Partial<RunStore>): void;
};

export function createRunStateSlice(set: SetState, get: () => RunStore): Omit<RunStore, "startAnalysis"> {
  const base = initialRunState();
  return {
    ...base,
    ws: null,
    setSymbol: (symbol) => set({ symbol }),
    resetRun: () =>
      set({
        ...initialRunState(),
        symbol: get().symbol,
        ws: null,
      }),
    setRunMeta: (runId, runStatus) => set({ runId, runStatus }),
    setWebSocket: (ws) => set({ ws }),
    applyEvent: (event) => {
      set((state) => applyEventToState(state, event));
    },
  };
}
