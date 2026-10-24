"use client";
import { useState } from "react";
import { ApiError, call } from "../../hooks/useApi";
import { AdminPage } from "./AdminPage";
import type { Release } from "@/lib/types";

export function Releases() {
  const [message, setMessage] = useState<string | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  return (
    <AdminPage<Release[]> path="admin/releases" title="Configuration releases" subtitle="Each change creates a numbered release. Runs keep the release they started with.">
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
    </AdminPage>
  );
}
