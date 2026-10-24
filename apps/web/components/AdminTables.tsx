"use client";
import { useRef, useState } from "react";
import { ApiError, call, useLoad } from "./useApi";
import { Empty, ErrorNotice, Loading } from "./Async";
import { HBars } from "./Charts";
import { SkillFlowDiagram, SourceFlowDiagram } from "./diagrams";
import { Callout, PageHeader } from "./ui";
import { Icon } from "./icons";
import type { ModelRow, Release } from "@/lib/types";

function Wrapper<T>({ path, title, subtitle, children }: { path: string; title: string; subtitle?: string; children: (data: T, reload: () => void) => React.ReactNode }) {
  const { data, error, loading, reload } = useLoad<T>(path);
  return (
    <>
      <PageHeader title={title} subtitle={subtitle} />
      {loading && !data && <Loading />}
      {error && <ErrorNotice message={error} onRetry={reload} />}
      {data && children(data, reload)}
    </>
  );
}

const BLANK = { model_id: "", provider: "anthropic", api_key_secret: "", input_usd_per_million: "", output_usd_per_million: "", price_verified_on: "", supports_structured_output: true };

export function ModelRegistry() {
  const [results, setResults] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ tone: string; text: string } | null>(null);
  const [form, setForm] = useState(BLANK);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const dialog = useRef<HTMLDialogElement>(null);

  const fail = (e: unknown) => setMessage({ tone: "bad", text: e instanceof ApiError ? e.message : "Request failed" });
  const smoke = async (id: string) => {
    try {
      const r = await call<{ ok: boolean; latency_ms: number; cost_usd: number }>("POST", `admin/models/${encodeURIComponent(id)}/smoke-test`);
      setResults((s) => ({ ...s, [id]: `${r.ok ? "OK" : "No reply"} · ${r.latency_ms} ms · US$${r.cost_usd}` }));
    } catch (e) { setResults((s) => ({ ...s, [id]: e instanceof ApiError ? e.message : "Failed" })); }
  };

  return (
    <Wrapper<ModelRow[]> path="admin/models" title="Model registry" subtitle="Every AI model agents are allowed to use. Add, retire or switch off models without a deployment.">
      {(rows, reload) => {
        const register = async () => {
          try {
            await call("POST", "admin/models", {
              ...form,
              api_key_secret: form.api_key_secret || null,
              input_usd_per_million: Number(form.input_usd_per_million),
              output_usd_per_million: Number(form.output_usd_per_million),
              price_verified_on: form.price_verified_on || null,
            });
            dialog.current?.close(); setForm(BLANK);
            setMessage({ tone: "ok", text: "Model registered after a passing smoke test. It is available to bind now." }); reload();
          } catch (e) { fail(e); }
        };
        const setStatus = async (id: string, status: string) => {
          try { await call("PUT", `admin/models/${encodeURIComponent(id)}/status`, { status, reason: reasons[id] }); setMessage({ tone: "ok", text: `${id} is now ${status}.` }); reload(); }
          catch (e) { fail(e); }
        };
        const field = (name: keyof typeof BLANK, label: string, type = "text") => (
          <>
            <label htmlFor={`m-${name}`}>{label}</label>
            <input id={`m-${name}`} type={type} value={String(form[name])} onChange={(e) => setForm({ ...form, [name]: e.target.value })} />
          </>
        );
        return (
          <>
            <p>Models can be added, deprecated or disabled at runtime. Only <em>active</em> models can be bound to an agent; deprecated models keep serving runs already pinned to them; disabled models serve nothing (runs use their approved fallback).</p>
            {message && <div className={`notice ${message.tone}`} role="status">{message.text}</div>}
            <button onClick={() => dialog.current?.showModal()}>Add model…</button>
            <div className="table-wrap"><table>
              <caption className="sr-only">Approved models</caption>
              <thead><tr><th>Model</th><th>Provider</th><th>Status</th><th>Price in/out per M tokens</th><th>Verified</th><th>Credential</th><th>Smoke test</th><th>Change status</th></tr></thead>
              <tbody>{rows.map((m) => (
                <tr key={m.model_id}><th scope="row">{m.model_id}</th><td>{m.provider}</td><td>{m.status}</td>
                  <td>${m.input_usd_per_million} / ${m.output_usd_per_million}</td><td>{m.price_verified_on ?? "fixture"}</td>
                  <td>{m.credential_status}</td>
                  <td><button className="secondary" onClick={() => smoke(m.model_id)}>Run</button> <span role="status">{results[m.model_id]}</span></td>
                  <td>
                    <label className="sr-only" htmlFor={`st-${m.model_id}`}>Reason for changing {m.model_id}</label>
                    <input id={`st-${m.model_id}`} placeholder="Reason" value={reasons[m.model_id] ?? ""} onChange={(e) => setReasons((s) => ({ ...s, [m.model_id]: e.target.value }))} />
                    {["active", "deprecated", "disabled"].filter((s) => s !== m.status).map((s) => (
                      <button key={s} className="secondary" disabled={!reasons[m.model_id]?.trim()} onClick={() => setStatus(m.model_id, s)}>Mark {s}</button>
                    ))}
                  </td></tr>
              ))}</tbody>
            </table></div>
            <dialog ref={dialog} aria-labelledby="add-h">
              <h2 id="add-h">Add a model</h2>
              <p className="hint">The provider endpoint is fixed by the platform. The API key must already exist in the parameter store; enter only its <em>name</em>.</p>
              <label htmlFor="m-provider">Provider</label>
              <select id="m-provider" value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}><option>anthropic</option><option>openai</option></select>
              {field("model_id", "Model id")}
              {field("api_key_secret", "API key parameter name (e.g. ANTHROPIC_API_KEY)")}
              {field("input_usd_per_million", "Input price, USD per million tokens", "number")}
              {field("output_usd_per_million", "Output price, USD per million tokens", "number")}
              {field("price_verified_on", "Prices verified on", "date")}
              {message?.tone === "bad" && <p className="field-error" role="alert">{message.text}</p>}
              <div className="row"><button onClick={register}>Smoke-test and register</button><button className="secondary" onClick={() => dialog.current?.close()}>Cancel</button></div>
            </dialog>
          </>
        );
      }}
    </Wrapper>
  );
}

interface SkillRow { skill_id: string; version: string; owner: string; approved: boolean; instructions: string; interpretation_limits: string; abstain_when: string; content_hash: string }
interface SkillsPayload { versions: Record<string, string>; hashes: Record<string, string>; skills: SkillRow[] }

function CopyHash({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <span className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
      <code title={value}>{value.slice(0, 12)}…</code>
      <button className="ghost" aria-label={`Copy fingerprint ${value}`} onClick={() => navigator.clipboard?.writeText(value).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}>
        {copied ? "Copied" : "Copy"}
      </button>
    </span>
  );
}

export function Skills() {
  return (
    <Wrapper<SkillsPayload> path="admin/skills" title="Skills" subtitle="Approved, versioned instructions that tell each agent how to do its job and when to stop.">
      {(d) => (
        <>
          <Callout tone="info" title="What a skill is">
            A skill is the written job description for one agent: what to do, what it must not conclude, and when to answer &quot;I don&apos;t know&quot;. Each is approved, versioned and fingerprinted. The active configuration release pins the exact version, so a past report can always show the text its agents followed. An agent cannot edit its own skill or widen its own permissions.
          </Callout>
          <section className="card" aria-labelledby="skill-flow-h">
            <h2 id="skill-flow-h">How a skill is used in a run</h2>
            <SkillFlowDiagram />
          </section>
          <div className="table-wrap"><table>
            <caption className="sr-only">Active skills</caption>
            <thead><tr><th>Skill</th><th>Agent</th><th>Version</th><th>Status</th><th>Fingerprint</th><th>Instructions</th></tr></thead>
            <tbody>{d.skills.map((s) => (
              <tr key={s.skill_id}>
                <th scope="row"><code>{s.skill_id}</code></th>
                <td>{s.owner}</td><td>{s.version}</td>
                <td><span className={`badge ${s.approved ? "ok" : "warn"}`}>{s.approved ? "Approved" : "Not approved"}</span></td>
                <td><CopyHash value={s.content_hash} /></td>
                <td>
                  <details><summary>View</summary>
                    <p><strong>Instructions:</strong> {s.instructions}</p>
                    <p><strong>Limits:</strong> {s.interpretation_limits}</p>
                    <p><strong>Abstains when:</strong> {s.abstain_when}</p>
                  </details>
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        </>
      )}
    </Wrapper>
  );
}

interface SourceRow { name: string; mode: string; snapshot: string; label?: string; agent?: string; protocol?: string; host?: string; provides?: string }
interface CheckResult { ok: boolean; records?: number; latency_ms?: number; detail?: string }

export function Sources() {
  const [checks, setChecks] = useState<Record<string, CheckResult | "pending">>({});
  const check = async (name: string) => {
    setChecks((s) => ({ ...s, [name]: "pending" }));
    const result = await call<CheckResult>("POST", `admin/sources/${name}/check`).catch(() => ({ ok: false, detail: "request failed" }) as CheckResult);
    setChecks((s) => ({ ...s, [name]: result }));
  };
  return (
    <Wrapper<SourceRow[]> path="admin/sources" title="Source health" subtitle="The public databases agents read from, how each is reached, and whether it is answering right now.">
      {(rows) => (
        <>
          <section className="card" aria-labelledby="source-flow-h">
            <h2 id="source-flow-h">How sources are reached</h2>
            <SourceFlowDiagram />
          </section>
          <div className="row" style={{ marginBottom: 12 }}>
            <button onClick={() => rows.forEach((r) => check(r.name))}>Check all sources</button>
            <span className="hint">Each check makes one small real request (Crohn&apos;s disease, NOD2).</span>
          </div>
          <div className="table-wrap"><table>
            <caption className="sr-only">Evidence sources</caption>
            <thead><tr><th>Source</th><th>What it provides</th><th>Used by</th><th>Access</th><th>Mode</th><th>Status</th><th><span className="sr-only">Action</span></th></tr></thead>
            <tbody>{rows.map((s) => {
              const c = checks[s.name];
              return (
                <tr key={s.name}>
                  <th scope="row">{s.label ?? s.name}<br /><code className="hint">{s.name}</code></th>
                  <td>{s.provides ?? "—"}</td>
                  <td>{s.agent ?? "—"}</td>
                  <td><span className="badge info">{s.protocol ?? "API"}</span><br /><code className="hint">{s.host}</code></td>
                  <td><span className={`badge ${s.mode === "live" ? "ok" : "warn"}`}>{s.mode === "live" ? "Live" : "Offline sample"}</span></td>
                  <td role="status">
                    {!c && <span className="hint">Not checked</span>}
                    {c === "pending" && <span className="hint">Checking…</span>}
                    {c && c !== "pending" && (c.ok
                      ? <span className="badge ok">Healthy · {c.latency_ms} ms · {c.records} {c.records === 1 ? "record" : "records"}</span>
                      : <span className="badge bad" title={c.detail}>Failing</span>)}
                    {c && c !== "pending" && !c.ok && <div className="field-error">{c.detail}</div>}
                  </td>
                  <td><button className="secondary" onClick={() => check(s.name)}>Check</button></td>
                </tr>
              );
            })}</tbody>
          </table></div>
        </>
      )}
    </Wrapper>
  );
}

export function Usage() {
  return (
    <Wrapper<{ total_usd: number; by_model: Record<string, number>; by_agent: Record<string, number> }> path="admin/usage" title="Usage & cost" subtitle="Estimated model spend from token counts. Compare with provider invoices.">
      {(d) => (
        <>
          <div className="grid cols-3" style={{ marginBottom: 18 }}><div className="kpi"><div className="ico"><Icon name="coin" size={22} /></div><div><div className="val">${d.total_usd.toFixed(4)}</div><div className="lbl">Total recorded spend</div></div></div></div>
          <div className="grid cols-2">
            <section className="card"><h2>By model</h2>{Object.keys(d.by_model).length ? <HBars data={d.by_model} /> : <Empty>No usage yet.</Empty>}</section>
            <section className="card"><h2>By agent</h2>{Object.keys(d.by_agent).length ? <HBars data={d.by_agent} /> : <Empty>No usage yet.</Empty>}</section>
          </div>
        </>
      )}
    </Wrapper>
  );
}

export function Audit() {
  return (
    <Wrapper<{ actor: string; action: string; detail: string; at: string }[]> path="admin/audit" title="Audit history" subtitle="An append-only record of every administrative change: who, what and why.">
      {(rows) => rows.length === 0 ? <Empty>No administrative changes recorded.</Empty> : (
        <div className="table-wrap"><table>
          <caption className="sr-only">Append-only administrative audit log</caption>
          <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Detail</th></tr></thead>
          <tbody>{[...rows].reverse().map((e, i) => <tr key={i}><td><time dateTime={e.at}>{new Date(e.at).toLocaleString()}</time></td><td>{e.actor}</td><td>{e.action}</td><td>{e.detail}</td></tr>)}</tbody>
        </table></div>
      )}
    </Wrapper>
  );
}

export function Releases() {
  const [message, setMessage] = useState<string | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  return (
    <Wrapper<Release[]> path="admin/releases" title="Configuration releases" subtitle="Each change creates a numbered release. Runs keep the release they started with.">
      {(rows, reload) => {
        const rollback = async (id: string) => {
          try { await call("POST", `admin/releases/${id}/rollback`, { reason: reasons[id] }); setMessage(`Rolled back to ${id} as a new release.`); reload(); }
          catch (e) { setMessage(e instanceof ApiError ? e.message : "Failed"); }
        };
        return (
          <>
            {message && <div className="notice" role="status">{message}</div>}
            <p>Rollback creates a new release copying an older one; history is never rewritten and old runs keep their original release.</p>
            <div className="table-wrap"><table>
              <caption className="sr-only">Release history</caption>
              <thead><tr><th>Release</th><th>Created</th><th>By</th><th>Reason</th><th>Rollback</th></tr></thead>
              <tbody>{[...rows].reverse().map((r) => (
                <tr key={r.release_id}><th scope="row">{r.release_id} (rev {r.revision})</th><td>{new Date(r.created_at).toLocaleString()}</td><td>{r.created_by}</td><td>{r.reason}</td>
                  <td><label className="sr-only" htmlFor={`rb-${r.release_id}`}>Reason for rollback to {r.release_id}</label>
                    <input id={`rb-${r.release_id}`} placeholder="Reason" value={reasons[r.release_id] ?? ""} onChange={(e) => setReasons((s) => ({ ...s, [r.release_id]: e.target.value }))} />
                    <button className="secondary" disabled={!reasons[r.release_id]?.trim()} onClick={() => rollback(r.release_id)}>Roll back to this</button></td></tr>
              ))}</tbody>
            </table></div>
          </>
        );
      }}
    </Wrapper>
  );
}
