import { cn } from "../lib/cn";
import type { AgentUiState } from "../types/events";

const STATUS_STYLES: Record<AgentUiState, string> = {
  idle: "bg-slate-700/40 text-slate-400",
  thinking: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  challenging: "bg-orange-500/20 text-orange-300 border-orange-500/40",
  deciding: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40",
  done: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  error: "bg-rose-500/20 text-rose-300 border-rose-500/40",
};

interface StatusChipProps {
  status: AgentUiState;
  label: string;
}

export function StatusChip({ status, label }: StatusChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        STATUS_STYLES[status],
      )}
    >
      {label}
    </span>
  );
}
