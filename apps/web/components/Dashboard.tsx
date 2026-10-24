"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyIllustration } from "./illustrations";
import { Kpi, PageHeader } from "./ui";
import { ProjectHistory } from "./RunHistory";
import { call } from "./useApi";
import { useProjects } from "./useProjects";
import type { RunSummary } from "@/lib/types";

export default function Dashboard() {
  const projectList = useProjects();
  const projects = (projectList.data ?? []).map((p) => p.project_id);
  const names = Object.fromEntries((projectList.data ?? []).map((p) => [p.project_id, p.name]));
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  useEffect(() => {
    if (!projectList.data) return;
    Promise.all(projects.map((p) => call<RunSummary[]>("GET", `projects/${p}/investigations`).catch(() => [])))
      .then((all) => setRuns(all.flat()));
  }, [projectList.data]);

  const count = (s: string) => runs?.filter((r) => r.status === s).length ?? "…";
  const spend = runs ? runs.reduce((t, r) => t + r.cost_usd, 0) : null;

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Your investigations at a glance. Start a new analysis, or open one to see its evidence, agents and report."
        actions={<Link className="button" href="/app/new">New analysis</Link>}
      />
      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <Kpi icon="list" value={runs?.length ?? "…"} label="Investigations" />
        <Kpi icon="pen" value={count("waiting_for_review")} label="Waiting for your review" />
        <Kpi icon="check" value={count("completed")} label="Approved reports" />
        <Kpi icon="coin" value={spend === null ? "…" : `$${spend.toFixed(2)}`} label="Model spend (estimate)" />
      </div>
      {projectList.data?.length === 0 && (
        <div className="card empty"><EmptyIllustration /><h2>Create your first project space</h2><p>A project is a private workspace for a disease or study. Create one, then start an analysis in it.</p><Link className="button" href="/app/projects">Create a project</Link></div>
      )}
      {runs?.length === 0 && projects.length > 0 && (
        <div className="card empty">
          <EmptyIllustration label="No investigations yet" />
          <h2>Run your first investigation</h2>
          <p>Pick a disease and up to five genes. A team of agents gathers the evidence and you get a draft report to review, usually within minutes.</p>
          <Link className="button" href="/app/new">Start an analysis</Link>
        </div>
      )}
      {projects.map((project) => (
        <section className="card" key={project} aria-labelledby={`p-${project}`}>
          <h2 id={`p-${project}`}>Project: {names[project] ?? project}</h2>
          <ProjectHistory projectId={project} />
        </section>
      ))}
    </>
  );
}
