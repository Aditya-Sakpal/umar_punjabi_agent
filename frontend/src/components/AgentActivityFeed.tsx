import { AGENT_ORDER } from "../store/runStore.logic";
import { useRunStore } from "../store";
import { AgentPanel } from "./AgentPanel";
import { EvidenceCards } from "./EvidenceCards";

export function AgentActivityFeed() {
  const agents = useRunStore((s) => s.agents);
  const evidence = useRunStore((s) => s.evidence);

  return (
    <section className="space-y-4" aria-label="Agent activity feed">
      <h2 className="text-xs font-semibold uppercase tracking-widest text-terminal-muted">
        Agent Activity
      </h2>
      <div className="grid gap-3">
        {AGENT_ORDER.map((name) => (
          <AgentPanel
            key={name}
            name={name}
            status={agents[name].status}
            tokens={agents[name].tokens}
            accent={name === "risk" ? "risk" : "default"}
          />
        ))}
      </div>
      <EvidenceCards items={evidence} />
    </section>
  );
}
