import { STAGES } from "@/lib/explain";
import type { RunEvent } from "@/lib/types";
import { Icon } from "./icons";

type Phase = "done" | "active" | "paused" | "stopped" | "todo";

export function stagePhases(events: RunEvent[], status: string): Phase[] {
  const finished = new Set(events.filter((e) => e.kind === "stage.completed").map((e) => e.data.stage as string));
  if (status === "completed") return STAGES.map(() => "done");
  const firstOpen = STAGES.findIndex((s) => !finished.has(s.id));
  return STAGES.map((_, i) => {
    if (i < firstOpen || firstOpen === -1) return "done";
    if (i > firstOpen) return "todo";
    if (status === "waiting_for_review") return "paused";
    if (["incomplete", "failed", "cancelled"].includes(status)) return "stopped";
    return "active";
  });
}

const ICON = { done: "check", paused: "pause", stopped: "cross", active: "clock", todo: "clock" } as const;
const WORD = { done: "Done", active: "In progress", paused: "Waiting for you", stopped: "Stopped here", todo: "Not started" };

/** The investigation as seven plain-language steps, so anyone can see where it is. */
export default function Stepper({ events, status }: { events: RunEvent[]; status: string }) {
  const phases = stagePhases(events, status);
  return (
    <ol className="stepper" aria-label="Investigation progress">
      {STAGES.map((stage, i) => (
        <li key={stage.id} className={`step ${phases[i]}`} aria-current={phases[i] === "active" ? "step" : undefined}>
          <div className="dot"><Icon name={phases[i] === "todo" ? stage.icon : ICON[phases[i]]} size={18} /></div>
          <strong>{stage.label}</strong>
          <span className="s">{WORD[phases[i]]}</span>
          <span className="s" title={stage.plain}>{stage.plain}</span>
        </li>
      ))}
    </ol>
  );
}
