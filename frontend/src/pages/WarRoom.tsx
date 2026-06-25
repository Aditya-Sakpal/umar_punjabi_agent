import { AgentActivityFeed } from "../components/AgentActivityFeed";
import { DecisionCard } from "../components/DecisionCard";
import { MarketSnapshotPanel } from "../components/MarketSnapshotPanel";
import { PortfolioCard } from "../components/PortfolioCard";
import { WarRoomHeader } from "../components/WarRoomHeader";
import { useRunStore } from "../store";

export function WarRoom() {
  const market = useRunStore((s) => s.market);
  const symbol = useRunStore((s) => s.symbol);
  const decision = useRunStore((s) => s.decision);
  const signal = useRunStore((s) => s.signal);
  const positions = useRunStore((s) => s.positions);
  const lastOrder = useRunStore((s) => s.lastOrder);
  const errors = useRunStore((s) => s.errors);

  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-4 p-4 md:p-6">
      <WarRoomHeader />

      {errors.length > 0 && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-950/40 px-4 py-2 text-sm text-rose-200">
          {errors.join(" · ")}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <AgentActivityFeed />
        </div>
        <div className="lg:col-span-2">
          <MarketSnapshotPanel symbol={symbol} market={market} />
        </div>
      </div>

      <DecisionCard decision={decision} signal={signal} />
      <PortfolioCard positions={positions} lastOrder={lastOrder} />
    </div>
  );
}
