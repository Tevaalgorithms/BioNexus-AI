"use client";
import { useRef, useState } from "react";
import { HBars } from "./Charts";
import { Callout, Kpi, PageHeader } from "./ui";
import { ApiError, call, useLoad } from "./useApi";
import { ErrorNotice, Loading } from "./Async";

interface Health { queue_depth: number; runs_by_status: Record<string, number>; emergency_stop: boolean }

export default function AdminOverview() {
  const health = useLoad<Health>("admin/health");
  const usage = useLoad<{ total_usd: number }>("admin/usage");
  const dialog = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (health.loading && !health.data) return <Loading />;
  if (health.error) return <ErrorNotice message={health.error} onRetry={health.reload} />;
  const h = health.data!;
  const total = Object.values(h.runs_by_status).reduce((a, b) => a + b, 0);
  const statuses = Object.fromEntries(Object.entries(h.runs_by_status).map(([k, v]) => [k.replaceAll("_", " "), v]));

  async function toggle() {
    try {
      await call("PUT", "admin/emergency-stop", { enabled: !h.emergency_stop, reason });
      dialog.current?.close(); setReason(""); setError(null); health.reload();
    } catch (e) { setError(e instanceof ApiError ? e.message : "Failed"); }
  }

  return (
    <>
      <PageHeader title="Platform overview" subtitle="The health of the platform at a glance: work in flight, spend, and the emergency control." />
      {h.emergency_stop && <Callout tone="bad" title="Emergency stop is ON">New model calls are blocked and affected runs end as incomplete. Nothing is silently rerouted to another model.</Callout>}
      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <Kpi icon="server" value={h.queue_depth} label="Jobs waiting in the queue" />
        <Kpi icon="list" value={total} label="Investigations recorded" />
        <Kpi icon="coin" value={`$${usage.data?.total_usd.toFixed(2) ?? "…"}`} label="Model spend (estimate)" />
        <Kpi icon={h.emergency_stop ? "stop" : "check"} value={h.emergency_stop ? "Stopped" : "Normal"} label="Model calls" />
      </div>
      <div className="grid cols-2">
        <section className="card"><h2>Investigations by status</h2>
          {total === 0 ? <p className="hint">Nothing has run yet.</p> : <HBars data={statuses} unit="" digits={0} />}</section>
        <section className="card"><h2>Emergency stop</h2>
          <p>Blocks every new model call across all investigations, for example during a provider incident or runaway spend. Runs in progress end as <em>incomplete</em> with their record preserved.</p>
          <button className={h.emergency_stop ? "" : "danger"} onClick={() => dialog.current?.showModal()}>{h.emergency_stop ? "Resume model calls…" : "Stop all model calls…"}</button></section>
      </div>
      <dialog ref={dialog} aria-labelledby="stop-h">
        <h2 id="stop-h">{h.emergency_stop ? "Resume model calls?" : "Stop all model calls?"}</h2>
        <label htmlFor="stop-reason">Reason (recorded in the audit log)</label>
        <input id="stop-reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        {error && <p className="field-error" role="alert">{error}</p>}
        <div className="row" style={{ marginTop: 14 }}><button disabled={!reason.trim()} onClick={toggle}>Confirm</button><button className="secondary" onClick={() => dialog.current?.close()}>Cancel</button></div>
      </dialog>
    </>
  );
}
