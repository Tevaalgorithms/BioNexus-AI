"use client";
import { useRef, useState } from "react";
import type { Report } from "@/lib/types";
import Markdown from "../ui/Markdown";
import { Icon } from "../ui/icons";
import { Callout } from "../ui/primitives";
import { ApiError, call } from "../../hooks/useApi";

export default function ReportTab({ runId, report, canApprove, onChanged }: { runId: string; report: Report; canApprove: boolean; onChanged: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  async function approve() {
    dialog.current?.close();
    try {
      await call("POST", `investigations/${runId}/report/approve`, { report_hash: report.content_hash });
      setMessage({ tone: "ok", text: "Report version approved." });
    } catch (error) {
      const text = error instanceof ApiError && error.status === 409
        ? "This report changed since you opened it. It has been reloaded; review it again before approving."
        : error instanceof ApiError ? error.message : "Could not approve.";
      setMessage({ tone: "bad", text });
    }
    onChanged();
  }

  const exportLink = (fmt: string, label: string) => (
    <a className="button secondary" href={`/api/proxy/investigations/${runId}/report/export?fmt=${fmt}`} download><Icon name="download" size={16} /> {label}</a>
  );

  return (
    <section aria-labelledby="report-h">
      <div className="page-head" style={{ marginBottom: 12 }}>
        <div><h2 id="report-h">Report, version {report.version}</h2>
          <span className={`badge ${report.status === "approved" ? "ok" : "warn"}`}>{report.status === "approved" ? `Approved by ${report.approved_by}` : "Draft: not scientist approved"}</span></div>
        <div className="row">
          {exportLink("docx", "Word")}{exportLink("md", "Markdown")}{exportLink("json", "Manifest")}
          {canApprove && report.status === "draft" && <button onClick={() => dialog.current?.showModal()}><Icon name="check" size={16} /> Approve this version…</button>}
        </div>
      </div>
      {message && <Callout tone={message.tone}>{message.text}</Callout>}
      {report.status === "draft" && <Callout tone="warn" title="How to read this draft">Counts are independent study families, not probabilities. Anything listed under <em>Limitations</em> is a known gap. Nothing here is a treatment recommendation.</Callout>}
      <Markdown source={report.markdown} />
      <dialog ref={dialog} aria-labelledby="confirm-h">
        <h2 id="confirm-h">Approve report version {report.version}?</h2>
        <p>You are approving this exact version (fingerprint <code>{report.content_hash.slice(0, 12)}</code>). Reviewed evidence becomes reusable in this project. Any later change creates a new version that needs its own approval.</p>
        <div className="row"><button onClick={approve}>Approve</button><button className="secondary" onClick={() => dialog.current?.close()}>Cancel</button></div>
      </dialog>
    </section>
  );
}
