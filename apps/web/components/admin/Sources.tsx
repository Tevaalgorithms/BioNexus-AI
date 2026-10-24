"use client";
import { useState } from "react";
import { call } from "../../hooks/useApi";
import { AdminPage } from "./AdminPage";
import { SourceFlowDiagram } from "./diagrams";

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
    <AdminPage<SourceRow[]> path="admin/sources" title="Source health" subtitle="The public databases agents read from, how each is reached, and whether it is answering right now.">
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
    </AdminPage>
  );
}
