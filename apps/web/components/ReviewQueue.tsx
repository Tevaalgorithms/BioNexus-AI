"use client";
import { ProjectHistory } from "./RunHistory";
import { Empty, ErrorNotice, Loading } from "./Async";
import { useProjects } from "./useProjects";

export default function ReviewQueue() {
  const { data, error, loading, reload } = useProjects();
  if (loading && !data) return <Loading what="projects" />;
  if (error) return <ErrorNotice message={error} onRetry={reload} />;
  if (!data?.length) return <Empty>You have no projects yet.</Empty>;
  return <>{data.map((p) => <section className="card" key={p.project_id}><h2>Project: {p.name}</h2><ProjectHistory projectId={p.project_id} onlyStatus="waiting_for_review" /></section>)}</>;
}
