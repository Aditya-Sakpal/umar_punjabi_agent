import { formatPrice } from "../lib/cn";
import type { OrderPayload, PositionRow } from "../types/events";

interface PortfolioCardProps {
  positions: PositionRow[];
  lastOrder: OrderPayload | null;
}

export function PortfolioCard({ positions, lastOrder }: PortfolioCardProps) {
  const totalPnl = positions.reduce((sum, p) => sum + p.pnl, 0);

  return (
    <section
      className="rounded-xl border border-terminal-border bg-terminal-panel/80 p-5"
      data-testid="portfolio-card"
    >
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-terminal-muted">
          Paper Portfolio
        </h2>
        <span
          className={`font-mono text-sm ${totalPnl >= 0 ? "text-terminal-buy" : "text-terminal-sell"}`}
        >
          PnL {totalPnl >= 0 ? "+" : ""}
          {formatPrice(totalPnl)}
        </span>
      </div>

      {lastOrder && (
        <p className="mb-3 text-xs text-slate-400">
          Last fill: {lastOrder.side} {lastOrder.qty} @ {formatPrice(Number(lastOrder.price ?? 0))}
        </p>
      )}

      {positions.length === 0 ? (
        <p className="text-sm text-slate-500 italic">No open simulated positions yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="pb-2 pr-4">Symbol</th>
                <th className="pb-2 pr-4">Side</th>
                <th className="pb-2 pr-4">Qty</th>
                <th className="pb-2 pr-4">Price</th>
                <th className="pb-2">PnL</th>
              </tr>
            </thead>
            <tbody className="font-mono text-slate-200">
              {positions.map((p) => (
                <tr key={p.id} className="border-t border-terminal-border/60">
                  <td className="py-2 pr-4">{p.symbol}</td>
                  <td className="py-2 pr-4">{p.side}</td>
                  <td className="py-2 pr-4">{p.qty}</td>
                  <td className="py-2 pr-4">{formatPrice(p.price)}</td>
                  <td className="py-2">{formatPrice(p.pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
