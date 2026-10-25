"use client";
import { useCallback, useState } from "react";
import ActivityFeed, { Timeline } from "./ActivityFeed";
import AgentTeam from "./AgentTeam";
import EvidenceTab from "./EvidenceTab";
import ReportTab from "./ReportTab";
import Stepper from "../ui/Stepper";
import StatusBadge from "../ui/StatusBadge";
import { Empty, ErrorNotice, Loading } from "../ui/Async";
import { Callout, InfoTip, Kpi } from "../ui/primitives";
import { ApiError, call, useLoad } from "../../hooks/useApi";
import { useRunEvents } from "../../hooks/useRunEvents";
import { statusSentence } from "@/lib/explain";
import type { Report, RunDetail } from "@/lib/types";

const TABS = ["Progress", "Evidence", "Report", "Team", "Limitations & sources", "Reproducibility"] as const;
const ACTIVE = new Set(["queued", "running"]);
const NO_REPORT = new Set(["queued", "running", "failed", "cancelled", "incomplete"]);

export default function RunView({ runId }: { runId: string }) {
  const detail = useLoad<RunDetail>(`investigations/${runId}/detail`);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Progress");
  const status = detail.data?.status;
  const report = useLoad<Report>(status && !NO_REPORT.has(status) ? `investigations/${runId}/report` : null);
  const { reload: reloadDetail } = detail;
  const { reload: reloadReport } = report;
  const refresh = useCallback(() => { reloadDetail(); reloadReport(); }, [reloadDetail, reloadReport]);
  const { events, mode } = useRunEvents(runId, refresh);
  const [cancelError, setCancelError] = useState<string | null>(null);

  if (detail.loading && !detail.data) return <Loading what="investigation" />;
  if (detail.error) return <ErrorNotice message={detail.error} onRetry={detail.reload} />;
  const d = detail.data!;
  const tone = d.status === "completed" ? "ok" : d.status === "failed" ? "bad" : ["incomplete", "waiting_for_review"].includes(d.status) ? "warn" : "info";

  async function cancel() {
    try { await call("POST", `investigations/${runId}/cancel`); setCancelError(null); refresh(); }
    catch (error) { setCancelError(error instanceof ApiError ? error.message : "Could not cancel."); }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>{d.disease}: {d.targets.join(", ")}</h1>
          <p className="lede">{d.question}</p>
        </div>
        <div className="row"><StatusBadge status={d.status} />{ACTIVE.has(d.status) && <button className="danger" onClick={cancel}>Cancel analysis</button>}</div>
      </header>
      <Callout tone={tone}>{statusSentence(d.status, d.stop_reason)}</Callout>
      {cancelError && <ErrorNotice message={cancelError} />}
      {d.budget_warning && <Callout tone="warn" title="Spend warning">This investigation passed its model-spend warning level. The hard limit will still stop it.</Callout>}

      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <Kpi icon="doc" value={d.evidence.filter((e) => e.accepted).length} label="Accepted evidence items" />
        <Kpi icon="alert" value={d.issues.length} label="Open issues" />
        <Kpi icon="link" value={d.timeline.filter((m) => m.type !== "task.result").length} label="Handoffs" />
        <Kpi icon="coin" value={`$${d.cost_usd.toFixed(4)}`} label="Model cost" />
      </div>

      <Stepper events={events} status={d.status} />

      <div role="tablist" aria-label="Investigation sections" className="tabs">
        {TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t}</button>)}
      </div>

      <div role="tabpanel">
        {tab === "Progress" && (<><div className="card"><ActivityFeed events={events} mode={mode} /></div><div className="card"><Timeline detail={d} /></div></>)}
        {tab === "Evidence" && (d.evidence.length ? <EvidenceTab detail={d} canRevise={d.status === "waiting_for_review"} onChanged={refresh} /> : <Empty>No evidence has been retrieved yet.</Empty>)}
        {tab === "Report" && (report.data ? <ReportTab runId={runId} report={report.data} canApprove={d.status === "waiting_for_review"} onChanged={refresh} /> : report.error ? <ErrorNotice message={report.error} onRetry={report.reload} /> : <Empty>The report appears once evidence gathering finishes.</Empty>)}
        {tab === "Team" && <AgentTeam detail={d} report={report.data} />}
        {tab === "Limitations & sources" && <Limitations d={d} />}
        {tab === "Reproducibility" && <Reproducibility report={report.data} d={d} />}
      </div>
    </>
  );
}

/** What the critic explained and what the verifier withheld. Both are model-assisted and unreviewed. */
function Reviews({ d }: { d: RunDetail }) {
  const explained = d.analyses.filter((a) => a.explanation);
  const withheld = d.verifications.filter((v) => v.verdict === "unsupported");
  const unchecked = d.verifications.filter((v) => v.verdict === "unchecked").length;
  return (
    <section className="card" aria-labelledby="reviews-h">
      <h2 id="reviews-h">Review notes <InfoTip label="review notes">Written by the critic and the verifier. A model helped write the explanations, so treat them as a prompt for your own judgement, not as a finding.</InfoTip></h2>
      <h3>Conflicts explained</h3>
      {explained.length === 0 ? <Empty>No conflict was explained.</Empty> : (
        <ul>{explained.map((a) => <li key={a.target}><strong>{a.target}</strong> <span className="badge info">{a.verdict}</span> {a.explanation} <span className="hint">(unreviewed)</span></li>)}</ul>
      )}
      <h3>Withheld by the verifier</h3>
      {withheld.length === 0 ? <Empty>Nothing was withheld.</Empty> : (
        <ul>{withheld.map((v) => <li key={v.subject}><strong>{v.kind === "claim" ? v.subject : "A summary sentence"}</strong>: {v.text} <span className="hint">Withheld because {v.reason || "the evidence does not support it"}.</span></li>)}</ul>
      )}
      {unchecked > 0 && <p className="hint">{unchecked} summary {unchecked === 1 ? "sentence" : "sentences"} could not be checked and {unchecked === 1 ? "is" : "are"} kept.</p>}
    </section>
  );
}

function Limitations({ d }: { d: RunDetail }) {
  return (
    <>
      <section className="card" aria-labelledby="sources-h">
        <h2 id="sources-h">Source completeness <InfoTip label="source completeness">Shows how much each database contributed. A source with no evidence means nothing eligible was found, or the source was unavailable. Gaps are shown, never hidden.</InfoTip></h2>
        <div className="table-wrap"><table>
          <caption className="sr-only">Evidence retained and excluded per source</caption>
          <thead><tr><th>Source</th><th>Retained</th><th>Excluded</th><th>Status</th></tr></thead>
          <tbody>{d.completeness.map((c) => (
            <tr key={c.source}><td>{c.source}</td><td>{c.retained}</td><td>{c.excluded}</td>
              <td>{c.status === "ok" ? <span className="badge ok">Evidence found</span> : <span className="badge warn">No evidence retrieved</span>}</td></tr>
          ))}</tbody>
        </table></div>
      </section>
      <Reviews d={d} />
      <section className="card" aria-labelledby="issues-h">
        <h2 id="issues-h">Open issues</h2>
        {d.issues.length === 0 ? <Empty>No open issues.</Empty> : <ul>{d.issues.map((i) => <li key={i.issue_id}>{i.description}</li>)}</ul>}
        <h2>Excluded evidence</h2>
        {d.excluded.length === 0 ? <Empty>Nothing excluded.</Empty> : <ul>{d.excluded.map((e) => <li key={e.evidence_id}><strong>{e.evidence_id}</strong>: {e.reason}</li>)}</ul>}
        <h2>Proposed next experiments</h2>
        <ul>{d.next_steps.map((s) => <li key={s}>{s}</li>)}{d.next_steps.length === 0 && <li>None.</li>}</ul>
      </section>
    </>
  );
}

function Reproducibility({ report, d }: { report?: Report; d: RunDetail }) {
  const m = report?.manifest;
  const hash = (obj?: Record<string, string>) => (obj ? Object.entries(obj).map(([k, v]) => `${k} ${v.slice(0, 8)}`).join(", ") : "n/a");
  return (
    <section className="card" aria-labelledby="repro-h">
      <h2 id="repro-h">Reproducibility <InfoTip label="reproducibility">Everything needed to explain or rerun this result: the exact configuration, skill versions, source snapshots and every model call.</InfoTip></h2>
      <dl className="facts">
        <dt>Configuration release</dt><dd>{d.release_id}</dd>
        <dt>Report version</dt><dd>{report ? `${report.version} (${report.status})` : "n/a"}</dd>
        <dt>Report fingerprint</dt><dd><code>{report?.content_hash ?? "n/a"}</code></dd>
        <dt>Model calls</dt><dd>{m?.model_calls?.length ?? 0}</dd>
        <dt>Models actually used</dt><dd>{[...new Set<string>((m?.model_calls ?? []).map((c: any) => `${c.agent}: ${c.model_id}${c.fallback_reason ? " (fallback)" : ""}`))].join("; ") || "n/a"}</dd>
        <dt>Skill fingerprints</dt><dd>{hash(m?.skill_hashes)}</dd>
        <dt>Source snapshots</dt><dd>{hash(m?.source_snapshots)}</dd>
      </dl>
      {d.graph_context.length > 0 && (<><h3 style={{ marginTop: 16 }}>Evidence graph context (up to 2 hops)</h3><p className="hint">Connections are for orientation only. Connectivity is not evidence of mechanism.</p><ul>{d.graph_context.slice(0, 20).map((e) => <li key={e}>{e}</li>)}</ul></>)}
    </section>
  );
}
