"use client";
import Link from "next/link";
import { Suspense } from "react";
import DataTable, { Column } from "./DataTable";
import StatusBadge from "./StatusBadge";
import { Empty, ErrorNotice, Loading } from "./Async";
import { useLoad } from "./useApi";
import type { RunSummary } from "@/lib/types";

const COLUMNS: Column<RunSummary>[] = [
  { key: "disease", header: "Investigation", sortValue: (r) => r.disease, filterText: (r) => `${r.disease} ${r.targets.join(" ")}`,
    render: (r) => <Link href={`/app/runs/${r.run_id}`}>{r.disease}: {r.targets.join(", ")}</Link> },
  { key: "status", header: "Status", sortValue: (r) => r.status, filterText: (r) => r.status, render: (r) => <StatusBadge status={r.status} /> },
  { key: "created", header: "Started", sortValue: (r) => r.created_at, render: (r) => <time dateTime={r.created_at}>{new Date(r.created_at).toLocaleString()}</time> },
  { key: "cost", header: "Model cost (USD)", sortValue: (r) => r.cost_usd, render: (r) => r.cost_usd.toFixed(4) },
];

export function ProjectHistory({ projectId, onlyStatus }: { projectId: string; onlyStatus?: string }) {
  const { data, error, loading, reload } = useLoad<RunSummary[]>(`projects/${projectId}/investigations`);
  if (loading) return <Loading what="investigations" />;
  if (error) return <ErrorNotice message={error} onRetry={reload} />;
  const rows = (data ?? []).filter((r) => !onlyStatus || r.status === onlyStatus);
  if (rows.length === 0) return <Empty>{onlyStatus ? "Nothing is waiting for review right now." : <>No investigations in this project yet. <Link href="/app/new">Start a new analysis</Link>.</>}</Empty>;
  return (
    <Suspense fallback={<Loading />}>
      <DataTable rows={rows} columns={COLUMNS} caption={`Investigations in ${projectId}`} rowKey={(r) => r.run_id} />
    </Suspense>
  );
}
