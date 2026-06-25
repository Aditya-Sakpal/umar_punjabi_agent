import { agentLabel, agentStatusLabel } from "../store/runStore.logic";
import type { AgentName, AgentUiState } from "../types/events";
import { StatusChip } from "./StatusChip";

interface AgentPanelProps {
  name: AgentName;
  status: AgentUiState;
  tokens: string;
  accent?: "default" | "risk";
}

export function AgentPanel({ name, status, tokens, accent = "default" }: AgentPanelProps) {
  const border =
    accent === "risk" ? "border-orange-500/30 shadow-[0_0_24px_-8px_rgba(251,146,60,0.35)]" : "border-terminal-border";

  return (
    <article className={`rounded-xl border bg-terminal-panel/80 p-4 ${border}`}>
      <header className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-200">{agentLabel(name)}</h3>
        <StatusChip status={status} label={agentStatusLabel(status)} />
      </header>
      <div
        className="min-h-[5rem] max-h-40 overflow-y-auto font-mono text-xs leading-relaxed text-slate-300 whitespace-pre-wrap"
        data-testid={`agent-tokens-${name}`}
      >
        {tokens || (
          <span className="text-terminal-muted italic">
            {status === "idle" ? "Waiting for run..." : "Streaming reasoning..."}
          </span>
        )}
      </div>
    </article>
  );
}
