import { AGENTS, SOURCE_LABELS } from "@/lib/explain";
import type { Report, RunDetail } from "@/lib/types";
import { Icon } from "./icons";

/** Who did what in this run, with the model each agent actually used (from the manifest). */
export default function AgentTeam({ detail, report }: { detail: RunDetail; report?: Report }) {
  const calls: any[] = report?.manifest?.model_calls ?? [];
  return (
    <div className="grid cols-2">
      {AGENTS.map((agent) => {
        const retained = detail.evidence.filter((e) => agent.sources.includes(e.source)).length;
        const received = detail.timeline.filter((m) => m.to === agent.id).length;
        const models = [...new Set(calls.filter((c) => c.agent === agent.id).map((c) => c.model_id))];
        return (
          <article className="card agent" key={agent.id} aria-labelledby={`agent-${agent.id}`}>
            <div className="ico"><Icon name={agent.icon} size={22} /></div>
            <div>
              <h3 id={`agent-${agent.id}`}>{agent.name}</h3>
              <p>{agent.role}</p>
              <div className="meta">
                <span>Sources: {agent.sources.length ? agent.sources.map((s) => SOURCE_LABELS[s]).join(", ") : agent.sourcesText}</span>
                {agent.sources.length > 0 && <span>Evidence kept: <strong>{retained}</strong></span>}
                <span>Tasks received: <strong>{received}</strong></span>
                {models.length > 0 && <span>Model: <strong>{models.join(", ")}</strong></span>}
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
