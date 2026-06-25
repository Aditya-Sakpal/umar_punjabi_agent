import type { EvidenceItem } from "../types/events";

interface EvidenceCardsProps {
  items: EvidenceItem[];
}

export function EvidenceCards({ items }: EvidenceCardsProps) {
  if (!items.length) return null;

  return (
    <div className="space-y-2" data-testid="evidence-cards">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-terminal-muted">
        Evidence
      </h3>
      <div className="flex flex-wrap gap-2">
        {items.map((item, i) => (
          <div
            key={`${item.source}-${item.claim}-${i}`}
            className="rounded-lg border border-terminal-border bg-slate-900/60 px-3 py-2 text-xs"
          >
            <div className="font-semibold text-cyan-300/90">{item.source}</div>
            <div className="text-slate-400">{item.claim}</div>
            <div className="font-mono text-slate-200">{String(item.value ?? "—")}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
