import type { MarketSnapshot } from "../store/runStore.logic";

interface MarketSnapshotPanelProps {
  symbol: string;
  market: MarketSnapshot;
}

export function MarketSnapshotPanel({ symbol, market }: MarketSnapshotPanelProps) {
  const rows = [
    { label: `${symbol} Price`, value: market.price },
    { label: "Funding", value: market.funding },
    { label: "Volume", value: market.volume },
    { label: "Sentiment", value: market.sentiment },
  ];

  return (
    <section
      className="rounded-xl border border-terminal-border bg-terminal-panel/80 p-4"
      aria-label="Live market snapshot"
    >
      <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-terminal-muted">
        Market Snapshot
      </h2>
      <dl className="grid grid-cols-2 gap-3">
        {rows.map((row) => (
          <div key={row.label} className="rounded-lg bg-slate-900/50 px-3 py-2">
            <dt className="text-[10px] uppercase tracking-wide text-slate-500">{row.label}</dt>
            <dd className="font-mono text-sm text-slate-100">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
