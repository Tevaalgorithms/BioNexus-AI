"use client";
import type { RunDetail, RunEvent } from "@/lib/types";
import { AGENTS, STAGES } from "@/lib/explain";

const agentName = (id: string) => AGENTS.find((a) => a.id === id)?.name ?? id;
const stageName = (id: string) => STAGES.find((s) => s.id === id)?.label ?? id;

/** What a challenge asked for: a missing passage, or a second look at a direction a model read. */
const challengeKind = (ask?: string | null) => (ask?.includes("recheck") ? "Second look" : "Missing passage");

function describe(e: RunEvent): string {
  if (e.kind === "stage.completed") return `Finished: ${stageName(e.data.stage)}`;
  if (e.kind === "agent.handoff") {
    const verbs: Record<string, string> = { "evidence.challenge": "challenged", "evidence.request": "asked for more evidence from", "task.result": "replied to" };
    const verb = verbs[e.data.type] ?? "asked";
    const detail = e.data.type === "evidence.challenge" ? ` (${challengeKind(e.data.ask).toLowerCase()})` : e.data.hint ? ` (“${e.data.hint}”)` : "";
    return `${agentName(e.data.from)} ${verb} ${agentName(e.data.to)}${detail}`;
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
      <h2 id="handoffs-h">Handoffs</h2>
      <p className="hint">Every request between team members is recorded. Replies are included so you can follow each conversation.</p>
      <div className="table-wrap"><table>
        <caption className="sr-only">Messages routed between team members</caption>
        <thead><tr><th>From</th><th>To</th><th>What</th><th>Evidence</th></tr></thead>
        <tbody>{detail.timeline.map((m) => (
          <tr key={m.message_id}><td>{agentName(m.from)}</td><td>{agentName(m.to)}</td>
            <td>{m.type === "task.request" ? "Task" : m.type === "task.result" ? "Reply" : m.type === "evidence.challenge" ? `Challenge: ${challengeKind(m.ask).toLowerCase()}` : m.type === "evidence.request" ? `Request: more evidence${m.hint ? ` (“${m.hint}”)` : ""}` : m.type}</td>
            <td>{m.evidence_ids.join(", ") || "-"}</td></tr>
        ))}</tbody>
      </table></div>
    </section>
  );
}
