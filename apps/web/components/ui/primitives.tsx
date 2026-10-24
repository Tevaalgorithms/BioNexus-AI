"use client";
import { ReactNode, useId, useState } from "react";
import { Icon, IconName } from "./icons";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-head">
      <div><h1>{title}</h1>{subtitle && <p className="lede">{subtitle}</p>}</div>
      {actions && <div className="row">{actions}</div>}
    </header>
  );
}

export function Kpi({ icon, value, label }: { icon: IconName; value: ReactNode; label: string }) {
  return (
    <div className="kpi">
      <div className="ico"><Icon name={icon} size={22} /></div>
      <div><div className="val">{value}</div><div className="lbl">{label}</div></div>
    </div>
  );
}

export function Callout({ tone = "info", icon, title, children }: { tone?: "info" | "warn" | "bad" | "ok"; icon?: IconName; title?: string; children: ReactNode }) {
  const defaults: Record<string, IconName> = { info: "info", warn: "alert", bad: "alert", ok: "check" };
  return (
    <div className={`callout ${tone}`} role={tone === "bad" ? "alert" : "note"}>
      <Icon name={icon ?? defaults[tone]} />
      <div>{title && <strong>{title}</strong>}<p>{children}</p></div>
    </div>
  );
}

/** A tap/click/keyboard-friendly help bubble (no hover-only content). */
export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="tip" onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
      <button type="button" aria-expanded={open} aria-controls={id} aria-label={`What is ${label}?`} onClick={() => setOpen(!open)}>?</button>
      {open && <span id={id} role="note" className="bubble">{children}</span>}
    </span>
  );
}

export function Section({ title, hint, children }: { title: string; hint?: ReactNode; children: ReactNode }) {
  return <section className="card"><h2>{title}</h2>{hint && <p className="hint" style={{ marginBottom: 12 }}>{hint}</p>}{children}</section>;
}
