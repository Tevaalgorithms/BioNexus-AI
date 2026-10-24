"use client";
import { useRef, useState } from "react";
import { ApiError, call } from "../../hooks/useApi";
import { AdminPage } from "./AdminPage";
import type { ModelRow } from "@/lib/types";

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
    <AdminPage<ModelRow[]> path="admin/models" title="Model registry" subtitle="Every AI model agents are allowed to use. Add, retire or switch off models without a deployment.">
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
    </AdminPage>
  );
}
