import { create } from "zustand";
import { startStreamRun } from "../api/client";
import { connectRunWebSocket } from "../api/ws";
import type { WSEvent } from "../types/events";
import { createRunStateSlice, initialRunState, type RunStore } from "./runStore";

export const useRunStore = create<RunStore>((set, get) => {
  const slice = createRunStateSlice(set, get);

  return {
    ...slice,
    async startAnalysis() {
      const { symbol, ws } = get();
      ws?.close();
      set({ ...initialRunState(), symbol, market: slice.market, ws: null, runStatus: "connecting" });

      try {
        const { run_id } = await startStreamRun(symbol);
        set({ runId: run_id, runStatus: "running" });

        const socket = connectRunWebSocket({
          runId: run_id,
          onEvent: (event: WSEvent) => get().applyEvent(event),
          onClose: (reason) => {
            if (reason === "error") set({ runStatus: "failed", ws: null });
            else set({ ws: null });
          },
          onError: () => set({ runStatus: "failed", ws: null }),
        });
        set({ ws: socket });
      } catch (e) {
        set({
          runStatus: "failed",
          errors: [...get().errors, String(e)],
        });
      }
    },
  };
});
