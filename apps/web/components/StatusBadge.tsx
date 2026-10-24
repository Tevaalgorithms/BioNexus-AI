import { Icon, IconName } from "./icons";

const MAP: Record<string, { tone: string; icon: IconName; label: string }> = {
  queued: { tone: "info", icon: "clock", label: "Queued" },
  running: { tone: "info", icon: "spark", label: "Running" },
  waiting_for_review: { tone: "warn", icon: "pen", label: "Needs your review" },
  completed: { tone: "ok", icon: "check", label: "Approved" },
  incomplete: { tone: "warn", icon: "alert", label: "Incomplete" },
  failed: { tone: "bad", icon: "cross", label: "Failed" },
  cancelled: { tone: "bad", icon: "stop", label: "Cancelled" },
  superseded: { tone: "info", icon: "link", label: "Superseded" },
};

/** Status is conveyed by an icon and words as well as colour. */
export default function StatusBadge({ status }: { status: string }) {
  const entry = MAP[status] ?? { tone: "info", icon: "info" as IconName, label: status };
  return <span className={`badge ${entry.tone}`}><Icon name={entry.icon} size={14} />{entry.label}</span>;
}
