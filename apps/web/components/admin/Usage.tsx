"use client";
import { AdminPage } from "./AdminPage";
import { Empty } from "../ui/Async";
import { HBars } from "../ui/Charts";
import { Icon } from "../ui/icons";

export function Usage() {
  return (
    <AdminPage<{ total_usd: number; by_model: Record<string, number>; by_agent: Record<string, number> }> path="admin/usage" title="Usage & cost" subtitle="Estimated model spend from token counts. Compare with provider invoices.">
      {(d) => (
        <>
          <div className="grid cols-3" style={{ marginBottom: 18 }}><div className="kpi"><div className="ico"><Icon name="coin" size={22} /></div><div><div className="val">${d.total_usd.toFixed(4)}</div><div className="lbl">Total recorded spend</div></div></div></div>
          <div className="grid cols-2">
            <section className="card"><h2>By model</h2>{Object.keys(d.by_model).length ? <HBars data={d.by_model} /> : <Empty>No usage yet.</Empty>}</section>
            <section className="card"><h2>By agent</h2>{Object.keys(d.by_agent).length ? <HBars data={d.by_agent} /> : <Empty>No usage yet.</Empty>}</section>
          </div>
        </>
      )}
    </AdminPage>
  );
}
