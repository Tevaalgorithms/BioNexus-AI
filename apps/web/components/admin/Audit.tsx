"use client";
import { AdminPage } from "./AdminPage";
import { Empty } from "../ui/Async";

export function Audit() {
  return (
    <AdminPage<{ actor: string; action: string; detail: string; at: string }[]> path="admin/audit" title="Audit history" subtitle="An append-only record of every administrative change: who, what and why.">
      {(rows) => rows.length === 0 ? <Empty>No administrative changes recorded.</Empty> : (
        <div className="table-wrap"><table>
          <caption className="sr-only">Append-only administrative audit log</caption>
          <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Detail</th></tr></thead>
          <tbody>{[...rows].reverse().map((e, i) => <tr key={i}><td><time dateTime={e.at}>{new Date(e.at).toLocaleString()}</time></td><td>{e.actor}</td><td>{e.action}</td><td>{e.detail}</td></tr>)}</tbody>
        </table></div>
      )}
    </AdminPage>
  );
}
