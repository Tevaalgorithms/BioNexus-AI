"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import CreateProjectDialog, { CreateProjectHandle } from "./CreateProjectDialog";
import { Icon } from "../ui/icons";
import { EmptyIllustration } from "../ui/illustrations";
import { Empty, ErrorNotice, Loading } from "../ui/Async";
import { PageHeader } from "../ui/primitives";
import { ApiError, call } from "../../hooks/useApi";
import { ProjectRow, useProjects } from "../../hooks/useProjects";

function Members({ project }: { project: ProjectRow }) {
  const [members, setMembers] = useState<string[] | null>(null);
  const [invite, setInvite] = useState("");
  const [message, setMessage] = useState<{ tone: string; text: string } | null>(null);

  async function load() {
    try { setMembers(await call<string[]>("GET", `projects/${project.project_id}/members`)); }
    catch (e) { setMessage({ tone: "bad", text: e instanceof ApiError ? e.message : "Could not load members." }); }
  }
  async function add() {
    try {
      setMembers(await call<string[]>("POST", `projects/${project.project_id}/members`, { user_id: invite }));
      setMessage({ tone: "ok", text: `${invite} can now open this project.` }); setInvite("");
    } catch (e) { setMessage({ tone: "bad", text: e instanceof ApiError ? e.message : "Could not add that person." }); }
  }
  return (
    <details onToggle={(e) => (e.currentTarget as HTMLDetailsElement).open && load()}>
      <summary>Members{members ? ` (${members.length})` : ""}</summary>
      {members && <p>{members.join(", ")}</p>}
      {project.owner && (
        <div>
          <label htmlFor={`inv-${project.project_id}`}>Invite a colleague by user id</label>
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <input id={`inv-${project.project_id}`} value={invite} onChange={(e) => setInvite(e.target.value)} placeholder="their user id" />
            <button className="secondary" disabled={!invite.trim()} onClick={add}>Add</button>
          </div>
          <p className="hint">They must already have a BioNexus scientist account in your organisation.</p>
        </div>
      )}
      {message && <p className={message.tone === "ok" ? "hint" : "field-error"} role="status">{message.text}</p>}
    </details>
  );
}

export default function ProjectsPage() {
  const { data, error, loading, reload } = useProjects();
  const creator = useRef<CreateProjectHandle>(null);
  return (
    <>
      <PageHeader
        title="Projects"
        subtitle="A project is a private workspace for one disease or study. Create one for each new disease you want to analyse, and invite the colleagues who should see it."
        actions={<button onClick={() => creator.current?.open()}><Icon name="plus" size={16} /> New project</button>}
      />
      <CreateProjectDialog ref={creator} onCreated={() => reload()} />
      {loading && !data && <Loading what="projects" />}
      {error && <ErrorNotice message={error} onRetry={reload} />}
      {data?.length === 0 && <div className="card empty"><EmptyIllustration /><h2>No projects yet</h2><p>Create your first project space to start analysing.</p></div>}
      <div className="grid cols-2">
        {data?.map((p) => (
          <article className="card" key={p.project_id} aria-labelledby={`pr-${p.project_id}`}>
            <div className="row"><h2 id={`pr-${p.project_id}`} style={{ margin: 0 }}>{p.name}</h2>{p.owner && <span className="badge info">Owner</span>}</div>
            <p className="hint">{p.description || "No description."} · id <code>{p.project_id}</code></p>
            <div className="row" style={{ margin: "8px 0" }}><Link className="button" href="/app/new">Start an analysis</Link></div>
            <Members project={p} />
          </article>
        ))}
      </div>
      <Empty>Reviewed evidence is reused only inside the project where it was approved, so each disease stays clean.</Empty>
    </>
  );
}
