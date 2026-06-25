import { formatConfidence } from "../lib/cn";
import type { DecisionPayload, SignalPayload } from "../types/events";

interface DecisionCardProps {
  decision: DecisionPayload | null;
  signal: SignalPayload | null;
}

export function DecisionCard({ decision, signal }: DecisionCardProps) {
  const action = decision?.action ?? "—";
  const confidence = decision?.confidence ?? signal?.confidence;
  const actionColor =
    action === "BUY"
      ? "text-terminal-buy"
      : action === "SELL"
        ? "text-terminal-sell"
        : "text-slate-300";

  return (
    <section
      className="rounded-xl border border-terminal-border bg-gradient-to-br from-slate-900/90 to-terminal-panel p-5"
      data-testid="decision-card"
    >
      <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-terminal-muted">
        Final Recommendation
      </h2>
      {!decision ? (
        <p className="text-sm text-slate-500 italic">Awaiting committee decision...</p>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-baseline gap-3">
            <span className={`text-4xl font-bold tracking-tight ${actionColor}`}>{action}</span>
            {confidence != null && (
              <span className="text-lg text-slate-300">{formatConfidence(confidence)} confidence</span>
            )}
          </div>
          {decision.size_pct > 0 && (
            <p className="text-sm text-slate-400">
              Size {decision.size_pct}% · Stop {decision.stop_loss_pct}%
            </p>
          )}
          <div>
            <h3 className="text-xs uppercase text-slate-500">Reasoning</h3>
            <p className="mt-1 text-sm leading-relaxed text-slate-200">{decision.rationale}</p>
          </div>
        </div>
      )}
    </section>
  );
}
