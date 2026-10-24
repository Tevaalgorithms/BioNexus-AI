"use client";
import { useState } from "react";
import type { RunDetail } from "@/lib/types";
import { SOURCE_LABELS, STANCE_HELP, STANCE_LABEL } from "@/lib/explain";
import { StanceChart, StanceLegend } from "../ui/Charts";
import { Icon } from "../ui/icons";
import { Callout, InfoTip } from "../ui/primitives";
import { ApiError, call } from "../../hooks/useApi";

export default function EvidenceTab({ detail, canRevise, onChanged }: { detail: RunDetail; canRevise: boolean; onChanged: () => void }) {
  const draftKey = `bn-exclude-reason-${detail.run_id}`;
  const [selected, setSelected] = useState<string[]>([]);
  const [reason, setReason] = useState(() => (typeof window === "undefined" ? "" : sessionStorage.getItem(draftKey) ?? ""));
  const [message, setMessage] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  const [showTable, setShowTable] = useState(false);

  const saveReason = (value: string) => {
    setReason(value);
    try { sessionStorage.setItem(draftKey, value); } catch { /* an unsent draft is only a convenience */ }
  };
  async function exclude() {
    try {
      await call("POST", `investigations/${detail.run_id}/report/exclusions`, { evidence_ids: selected, reason });
      sessionStorage.removeItem(draftKey);
      setSelected([]); setReason("");
      setMessage({ tone: "ok", text: "Evidence excluded. A new draft report version was created; review it before approving." });
      onChanged();
    } catch (error) {
      setMessage({ tone: "bad", text: error instanceof ApiError ? error.message : "Could not exclude evidence." });
    }
  }
  const toggle = (id: string) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  return (
    <>
      <section className="card" aria-labelledby="matrix-h">
        <h2 id="matrix-h">Evidence at a glance <InfoTip label="independent study families">Each bar counts <em>independent studies</em>. One paper that appears in several databases is counted once, so repetition is not mistaken for confirmation.</InfoTip></h2>
        <p className="hint">How many independent studies point each way, per gene. Only accepted evidence is counted.</p>
        <StanceLegend />
        <StanceChart rows={detail.matrix} />
        <button className="ghost" onClick={() => setShowTable(!showTable)} aria-expanded={showTable}><Icon name="list" size={16} /> {showTable ? "Hide" : "Show"} data table</button>
        {showTable && (
          <div className="table-wrap"><table>
            <caption className="sr-only">Supporting, opposing and undirected study families per target</caption>
            <thead><tr><th scope="col">Target</th><th scope="col">Supporting</th><th scope="col">Opposing</th><th scope="col">No direction</th><th scope="col">Net</th></tr></thead>
            <tbody>{detail.matrix.map((r) => (
              <tr key={r.target}><th scope="row">{r.target}</th><td>{r.supporting_families}</td><td>{r.opposing_families}</td><td>{r.unknown_families}</td><td>{STANCE_LABEL[r.net_stance]}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </section>

      <section aria-labelledby="cards-h">
        <h2 id="cards-h">Evidence behind the findings</h2>
        {message && <Callout tone={message.tone}>{message.text}</Callout>}
        {detail.evidence.map((e) => (
          <article className="card" key={e.evidence_id} aria-labelledby={`ev-${e.evidence_id}`}>
            <div className="row">
              {canRevise && <input type="checkbox" style={{ width: "auto" }} aria-label={`Select ${e.evidence_id} for exclusion`} checked={selected.includes(e.evidence_id)} onChange={() => toggle(e.evidence_id)} />}
              <strong id={`ev-${e.evidence_id}`}>{e.target}</strong>
              <span className="badge info">{SOURCE_LABELS[e.source] ?? e.source}</span>
              <span className="badge info" title={STANCE_HELP[e.stance]}>{STANCE_LABEL[e.stance]}</span>
              {!e.accepted && <span className="badge warn"><Icon name="alert" size={14} /> Not accepted: no supporting passage</span>}
              {e.review_state === "reviewed" && <span className="badge ok"><Icon name="check" size={14} /> Previously reviewed</span>}
            </div>
            <p style={{ margin: "10px 0 4px" }}>{e.finding}</p>
            {e.passage.length > 420 ? (
              <details className="passage"><summary>“{e.passage.slice(0, 420)}…” <span className="hint">Show full passage</span></summary>“{e.passage}”</details>
            ) : (
              <p className="passage">{e.passage ? `“${e.passage}”` : "No passage available."}</p>
            )}
            <p className="hint">{e.species} · {e.context} · study {e.study_family} · available {e.available_on} · id {e.evidence_id}</p>
          </article>
        ))}
        {canRevise && (
          <div className="card">
            <h3>Exclude evidence you do not trust</h3>
            <label htmlFor="reason">Reason for excluding {selected.length} selected item(s)</label>
            <input id="reason" value={reason} onChange={(e) => saveReason(e.target.value)} />
            <p className="hint">The reason is recorded in the audit log. Excluded evidence is also removed from future reuse in this project and a new draft version is created.</p>
            <button disabled={!selected.length || !reason.trim()} onClick={exclude} style={{ marginTop: 10 }}>Exclude and regenerate draft</button>
          </div>
        )}
      </section>
    </>
  );
}
