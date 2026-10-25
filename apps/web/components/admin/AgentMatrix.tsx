"use client";
import { useMemo, useRef, useState } from "react";
import { ApiError, call, useLoad } from "../../hooks/useApi";
import { ErrorNotice, Loading } from "../ui/Async";
import { Icon } from "../ui/icons";
import { ConfigFlowDiagram } from "./diagrams";
import { PageHeader } from "../ui/primitives";
import { AGENTS, SKILL_FOR } from "@/lib/explain";
import type { ModelRow, Release } from "@/lib/types";

interface Check { valid?: boolean; problems?: string[]; changes?: Record<string, string> }
interface Evaluation { status: string; stop_reason: string | null; model_calls: number; models_used: string[]; cost_usd: number; grounding_warnings: string[] }


const usesModel = (agent: string) => AGENTS.find((a) => a.id === agent)?.modelUse != null;

export default function AgentMatrix() {
  const release = useLoad<Release>("admin/release");
  const models = useLoad<ModelRow[]>("admin/models");
  const [editing, setEditing] = useState<string | null>(null);
  const [model, setModel] = useState("");
  const [fallback, setFallback] = useState("");
  const [reason, setReason] = useState("");
  const [check, setCheck] = useState<Check | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [message, setMessage] = useState<{ tone: string; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);

  const binding = useMemo(() => ({ model_id: model, fallback_model_id: fallback || null }), [model, fallback]);
  if ((release.loading && !release.data) || (models.loading && !models.data)) return <Loading />;
  if (release.error || models.error) return <ErrorNotice message={(release.error || models.error)!} onRetry={() => { release.reload(); models.reload(); }} />;
  const r = release.data!;

  function open(agent: string) {
    const current = r.bindings[agent];
    setEditing(agent); setModel(current.model_id); setFallback(current.fallback_model_id ?? "");
    setReason(""); setCheck(null); setEvaluation(null); setMessage(null);
    dialog.current?.showModal();
  }

  const body = () => ({ binding, reason, expected_revision: r.revision });
  async function run<T>(action: () => Promise<T>, done: (v: T) => void) {
    setBusy(true); setMessage(null);
    try { done(await action()); } catch (e) { setMessage({ tone: "bad", text: e instanceof ApiError ? e.message : "Request failed" }); } finally { setBusy(false); }
  }

  const validate = () => run(() => call<Check>("POST", `admin/agents/${editing}/binding/validate`, body()), setCheck);
  const evaluate = () => run(() => call<Evaluation>("POST", `admin/agents/${editing}/binding/evaluate`, body()), setEvaluation);
  const activate = () => run(() => call("PUT", `admin/agents/${editing}/binding`, body()), () => {
    dialog.current?.close(); setMessage({ tone: "ok", text: `Activated for new runs. Runs already in progress keep their original release.` }); release.reload();
  });

  return (
    <>
      <PageHeader title="Agents & models" subtitle={<>Which AI model the agents that call one use (literature and the synthesizer; the others are plain code). Active release <strong>{r.release_id}</strong> (revision {r.revision}). Changes apply to <em>new</em> runs only; runs in progress stay pinned to the release they started with.</>} />
      {message && !dialog.current?.open && <div className={`notice ${message.tone}`} role="status">{message.text}</div>}
      <section className="card" aria-labelledby="cfg-flow-h">
        <h2 id="cfg-flow-h">How these settings are used</h2>
        <p className="hint" style={{ marginBottom: 10 }}>A release fixes each agent&apos;s skill and model when a run starts. Every model call then passes through the gateway, which only allows approved models, applies the fallback and the budget, and records the call.</p>
        <ConfigFlowDiagram release={r} />
      </section>
      <div className="table-wrap"><table>
        <caption className="sr-only">Agent configuration matrix</caption>
        <thead><tr><th>Agent</th><th>Calls a model for</th><th>Primary model</th><th>Fallback</th><th>Skill version</th><th>Max output tokens</th><th><span className="sr-only">Actions</span></th></tr></thead>
        <tbody>{Object.entries(r.bindings).map(([agent, b]) => (
          <tr key={agent}><th scope="row"><span className="row" style={{ flexWrap: "nowrap" }}><Icon name={AGENTS.find((a) => a.id === agent)?.icon ?? "cpu"} size={18} /><span>{AGENTS.find((a) => a.id === agent)?.name ?? agent}<span className="hint" style={{ display: "block", fontWeight: 400 }}>{AGENTS.find((a) => a.id === agent)?.role}</span></span></span></th><td>{AGENTS.find((a) => a.id === agent)?.modelUse ?? <span className="hint">Nothing: plain code</span>}</td>
            <td>{usesModel(agent) ? b.model_id : <span className="hint">not used</span>}</td><td>{usesModel(agent) ? b.fallback_model_id ?? "none" : <span className="hint">not used</span>}</td>
            <td>{SKILL_FOR[agent]}@{r.skill_versions[SKILL_FOR[agent]]}</td><td>{b.max_output_tokens}</td>
            <td>{usesModel(agent) ? <button className="secondary" onClick={() => open(agent)}>Change {agent} model</button> : null}</td></tr>
        ))}</tbody>
      </table></div>

      <dialog ref={dialog} aria-labelledby="edit-h">
        <h2 id="edit-h">Change {editing} agent</h2>
        <label htmlFor="m">Primary model</label>
        <select id="m" value={model} onChange={(e) => { setModel(e.target.value); setCheck(null); setEvaluation(null); }}>
          {models.data!.map((m) => <option key={m.model_id}>{m.model_id}</option>)}
        </select>
        <label htmlFor="f">Approved fallback</label>
        <select id="f" value={fallback} onChange={(e) => { setFallback(e.target.value); setCheck(null); }}>
          <option value="">none</option>{models.data!.map((m) => <option key={m.model_id}>{m.model_id}</option>)}
        </select>
        <label htmlFor="why">Reason (required, audited)</label>
        <input id="why" value={reason} onChange={(e) => setReason(e.target.value)} />
        {message && <div className={`notice ${message.tone}`} role="alert">{message.text}</div>}
        {check && (
          <div className={`notice ${check.valid ? "ok" : "bad"}`} role="status">
            <strong>{check.valid ? "Valid" : "Not valid"}</strong>
            <ul>{(check.problems ?? []).map((p) => <li key={p}>{p}</li>)}</ul>
            <p>Before → after:</p>
            <ul>{Object.entries(check.changes ?? {}).map(([k, v]) => <li key={k}>{k}: {v}</li>)}{Object.keys(check.changes ?? {}).length === 0 && <li>No changes.</li>}</ul>
          </div>
        )}
        {evaluation && (
          <div className={`notice ${evaluation.status === "waiting_for_review" ? "ok" : "warn"}`} role="status">
            <strong>Fixture evaluation: {evaluation.status}</strong>
            <p>{evaluation.model_calls} model calls · models {evaluation.models_used.join(", ")} · cost US${evaluation.cost_usd} · grounding warnings: {evaluation.grounding_warnings.length}</p>
          </div>
        )}
        <div className="row">
          <button onClick={validate} disabled={busy}>1. Validate</button>
          <button onClick={evaluate} disabled={busy || !check?.valid}>2. Evaluate on fixtures</button>
          <button onClick={activate} disabled={busy || !check?.valid || !evaluation || !reason.trim()}>3. Activate</button>
          <button className="secondary" onClick={() => dialog.current?.close()}>Close</button>
        </div>
      </dialog>
    </>
  );
}
