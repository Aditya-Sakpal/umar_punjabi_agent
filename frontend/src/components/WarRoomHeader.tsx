import { universeSymbols } from "../api/client";
import { useRunStore } from "../store";

const RUN_STATUS_LABEL: Record<string, string> = {
  idle: "Ready",
  connecting: "Starting...",
  running: "Live",
  completed: "Completed",
  failed: "Failed",
};

export function WarRoomHeader() {
  const symbol = useRunStore((s) => s.symbol);
  const runId = useRunStore((s) => s.runId);
  const runStatus = useRunStore((s) => s.runStatus);
  const setSymbol = useRunStore((s) => s.setSymbol);
  const startAnalysis = useRunStore((s) => s.startAnalysis);
  const busy = runStatus === "connecting" || runStatus === "running";

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-terminal-border bg-terminal-panel/90 px-4 py-3">
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold tracking-tight text-cyan-300">War Room</span>
        <span className="hidden text-xs text-slate-500 sm:inline">Trading Intelligence Demo</span>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-slate-400">
          Asset
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            disabled={busy}
            className="rounded-lg border border-terminal-border bg-slate-900 px-3 py-1.5 text-sm text-slate-100"
          >
            {universeSymbols().map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          onClick={() => void startAnalysis()}
          disabled={busy}
          className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-50"
        >
          {busy ? "Running..." : "Analyze"}
        </button>

        <div className="text-right text-xs">
          <div className="text-slate-500">Run status</div>
          <div className="font-medium text-slate-200">{RUN_STATUS_LABEL[runStatus]}</div>
          {runId && <div className="font-mono text-[10px] text-slate-500">{runId.slice(0, 8)}…</div>}
        </div>
      </div>
    </header>
  );
}
