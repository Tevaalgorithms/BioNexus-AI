"use client";
import type { RunDetail, RunEvent } from "@/lib/types";
import { AGENTS, STAGES } from "@/lib/explain";

const agentName = (id: string) => AGENTS.find((a) => a.id === id)?.name ?? id;
const stageName = (id: string) => STAGES.find((s) => s.id === id)?.label ?? id;

function describe(e: RunEvent): string {
  if (e.kind === "stage.completed") return `Finished: ${stageName(e.data.stage)}`;
  if (e.kind === "agent.handoff") {
    const verb = e.data.type === "evidence.challenge" ? "challenged" : e.data.type === "task.result" ? "replied to" : "asked";
    return `${agentName(e.data.from)} ${verb} ${agentName(e.data.to)}`;
  }
  return `Run ${String(e.data.status).replaceAll("_", " ")}${e.data.reason ? `: ${e.data.reason}` : ""}`;
}

/** A readable log, announced politely to screen readers. */
export default function ActivityFeed({ events, mode }: { events: RunEvent[]; mode: "live" | "polling" }) {
  return (
    <section aria-labelledby="activity-h">
      <h2 id="activity-h">Activity log</h2>
      <p className="hint">{mode === "live" ? "Updating live." : "Live stream unavailable; checking every few seconds."}</p>
      <ol aria-live="polite" aria-relevant="additions" style={{ paddingLeft: 20 }}>
        {events.map((e) => <li key={e.seq}>{describe(e)}</li>)}
      </ol>
    </section>
  );
}

export function Timeline({ detail }: { detail: RunDetail }) {
  return (
    <section aria-labelledby="handoffs-h">
      <h2 id="handoffs-h">Agent handoffs</h2>
      <p className="hint">Every request between agents is recorded. Replies are included so you can follow each conversation.</p>
      <div className="table-wrap"><table>
        <caption className="sr-only">Messages routed between agents</caption>
        <thead><tr><th>From</th><th>To</th><th>What</th><th>Evidence</th></tr></thead>
        <tbody>{detail.timeline.map((m) => (
          <tr key={m.message_id}><td>{agentName(m.from)}</td><td>{agentName(m.to)}</td>
            <td>{m.type === "task.request" ? "Task" : m.type === "task.result" ? "Reply" : m.type === "evidence.challenge" ? "Challenge" : m.type}</td>
            <td>{m.evidence_ids.join(", ") || "-"}</td></tr>
        ))}</tbody>
      </table></div>
    </section>
  );
}
