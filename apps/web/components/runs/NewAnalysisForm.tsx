"use client";
import { FormEvent, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "../ui/icons";
import { Callout } from "../ui/primitives";
import CreateProjectDialog, { CreateProjectHandle } from "../projects/CreateProjectDialog";
import { useProjects } from "../../hooks/useProjects";
import { ApiError, call, useLoad } from "../../hooks/useApi";
import { PRESETS, coveredByDemo } from "@/lib/presets";
import { SOURCE_LABELS } from "@/lib/explain";

const GENE = /^[A-Za-z0-9-]{2,15}$/;

interface Errors { project?: string; disease?: string; targets?: string; question?: string; cutoff?: string; form?: string }
interface Meta { data_mode: "demo" | "live"; demo_diseases: string[]; model_mode: "demo" | "live"; sources: string[] }

export default function NewAnalysisForm() {
  const router = useRouter();
  const meta = useLoad<Meta>("meta").data;
  const projectList = useProjects();
  const projects = (projectList.data ?? []).map((p) => p.project_id);
  const creator = useRef<CreateProjectHandle>(null);
  const today = new Date().toISOString().slice(0, 10);
  const [values, setValues] = useState({ project: "", disease: PRESETS[0].disease, targets: PRESETS[0].targets, question: PRESETS[0].question, cutoff: today });
  const [errors, setErrors] = useState<Errors>({});
  const [busy, setBusy] = useState(false);
  const firstError = useRef<HTMLDivElement>(null);
  const set = (key: keyof typeof values) => (e: { target: { value: string } }) => setValues({ ...values, [key]: e.target.value });

  const project = values.project || projects[0] || "";
  const demo = meta?.data_mode === "demo";
  const uncovered = demo && !coveredByDemo(values.disease, meta?.demo_diseases ?? []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const targets = values.targets.split(",").map((t) => t.trim()).filter(Boolean);
    const found: Errors = {};
    if (!project) found.project = "Choose or create a project.";
    if (values.disease.trim().length < 2) found.disease = "Enter a disease name.";
    if (targets.length < 1 || targets.length > 5 || !targets.every((t) => GENE.test(t))) found.targets = "Enter 1–5 gene symbols separated by commas, for example NOD2, IL23R.";
    if (values.question.trim().length < 5) found.question = "Describe the research question (at least 5 characters).";
    if (!values.cutoff) found.cutoff = "Choose an evidence cutoff date.";
    setErrors(found);
    if (Object.keys(found).length) { queueMicrotask(() => firstError.current?.focus()); return; }

    setBusy(true);
    try {
      const body = { disease: values.disease, targets, question: values.question, evidence_cutoff: values.cutoff };
      const run = await call<{ run_id: string }>("POST", `projects/${project}/investigations`, body, { "idempotency-key": crypto.randomUUID() });
      router.push(`/app/runs/${run.run_id}`);
    } catch (error) {
      setErrors({ form: error instanceof ApiError ? error.message : "Could not start the analysis." });
      queueMicrotask(() => firstError.current?.focus());
    } finally { setBusy(false); }
  }

  const summary = Object.values(errors).filter(Boolean);
  return (
    <>
      <section className="card" aria-labelledby="what-h">
        <h2 id="what-h">What are we analysing?</h2>
        <p>You give a <strong>disease</strong> and up to five <strong>genes</strong>. BioNexus asks public databases one question: <em>is there published evidence linking each gene to this disease, which way does it point, and how many independent studies say so?</em></p>
        <div className="grid cols-3">
          <div><strong><Icon name="dna" size={16} /> Genetics</strong><p className="hint">Do variants in the gene associate with the disease? (Open Targets, GWAS Catalog)</p></div>
          <div><strong><Icon name="book" size={16} /> Literature &amp; pathways</strong><p className="hint">What do papers say, and which biological pathways is the gene part of? (Europe PMC, Reactome, Monarch)</p></div>
          <div><strong><Icon name="flask" size={16} /> Clinical trials</strong><p className="hint">Have trials been registered for this disease and gene? Registration does not mean a treatment works. (ClinicalTrials.gov)</p></div>
        </div>
        <p className="hint" style={{ marginTop: 10 }}>It does <strong>not</strong> test a drug, predict an individual patient&apos;s outcome, or prove a cause. You get a draft evidence report to review.</p>
      </section>

      {meta && (demo
        ? <Callout tone="warn" title="Demo data mode">Only a small offline sample is loaded, and it covers <strong>{meta.demo_diseases.join(", ")}</strong>. Other diseases will finish as <em>incomplete: no evidence found</em>. An administrator can switch on live public databases to analyse any disease.</Callout>
        : <Callout tone="ok" title="Live data mode">Any disease works. Genes are looked up in the public databases in real time, so a run takes about a minute.{meta.model_mode === "demo" && " The AI model is still a demo placeholder, so literature findings will show no stated direction until a real model is configured by an administrator."}</Callout>)}

      <CreateProjectDialog ref={creator} onCreated={(id) => { setValues((v) => ({ ...v, project: id })); projectList.reload(); }} />
      <div className="split">
        <form className="card" onSubmit={submit} noValidate aria-describedby="boundaries">
          <div id="boundaries" className="callout warn">
            <Icon name="shield" />
            <div><strong>Research-use boundaries</strong><p>Only public biomedical evidence and confidential research questions. Do not enter patient records or patient-level genomic data. Results are evidence assessments, never treatment recommendations.</p></div>
          </div>
          <h2>Start from an example, or type your own</h2>
          <div className="chips" role="group" aria-label="Example questions">
            {PRESETS.map((p) => (
              <button type="button" key={p.id} className="chip" onClick={() => setValues({ ...values, project: projects.find((id) => id === p.project || id.startsWith(`${p.project}-`)) ?? project, disease: p.disease, targets: p.targets, question: p.question })}>
                {p.label}{demo && p.id !== "crohns" ? " (live only)" : ""}
              </button>
            ))}
          </div>
          {summary.length > 0 && (
            <div className="callout bad" role="alert" tabIndex={-1} ref={firstError}>
              <Icon name="alert" /><div><strong>Please fix the following:</strong><ul>{summary.map((m) => <li key={m}>{m}</li>)}</ul></div>
            </div>
          )}
          <label htmlFor="project">Project</label>
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <select id="project" value={project} onChange={set("project")} aria-invalid={!!errors.project} aria-describedby="project-hint">
              {(projectList.data ?? []).map((p) => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
            </select>
            <button type="button" className="secondary" style={{ whiteSpace: "nowrap" }} onClick={() => creator.current?.open(values.disease)}><Icon name="plus" size={16} /> New project</button>
          </div>
          {projectList.data?.length === 0 && <p className="field-error" role="status">You have no project yet. Create one to start (for example one per disease or study).</p>}
          <p id="project-hint" className="hint">A project is a private workspace, not a disease. It decides who can see these results and where reviewed evidence is reused. Choose the project for your team or study; examples pick a matching one for you when you belong to it.</p>
          <label htmlFor="disease">Disease</label>
          <input id="disease" value={values.disease} onChange={set("disease")} aria-invalid={!!errors.disease} aria-describedby="disease-hint" />
          <p id="disease-hint" className="hint">Use the common name, for example COVID-19, Type 2 diabetes or Alzheimer&apos;s disease.</p>
          {uncovered && <p className="field-error" role="status">This disease is not in the demo data, so this run is expected to finish with no evidence.</p>}
          <label htmlFor="targets">Targets (genes)</label>
          <input id="targets" value={values.targets} onChange={set("targets")} aria-invalid={!!errors.targets} aria-describedby="targets-hint" />
          <p id="targets-hint" className="hint">Up to five official gene symbols separated by commas, for example ACE2, TMPRSS2.</p>
          <label htmlFor="question">Research question</label>
          <textarea id="question" rows={3} value={values.question} onChange={set("question")} aria-invalid={!!errors.question} />
          <label htmlFor="cutoff">Evidence cutoff</label>
          <input id="cutoff" type="date" value={values.cutoff} max={today} onChange={set("cutoff")} aria-invalid={!!errors.cutoff} />
          <p className="hint">Only evidence available on or before this date is used. Databases that do not date their records are treated as first seen today.</p>
          <p className="hint">Limits: up to US$10 model spend per investigation (warning at US$5), at most two repair rounds.</p>
          <button type="submit" disabled={busy} style={{ marginTop: 18 }}>{busy ? "Starting…" : "Start analysis"}</button>
        </form>
        <aside className="card" aria-labelledby="next-h">
          <h2 id="next-h">What happens next</h2>
          <ol style={{ paddingLeft: 20 }}>
            <li><strong>Gather:</strong> genetics, literature, pathway and trial agents search approved sources in parallel.</li>
            <li><strong>Challenge:</strong> a critic flags contradictions and missing support, and asks for repairs.</li>
            <li><strong>Draft:</strong> findings are written using only accepted evidence.</li>
            <li><strong>You decide:</strong> review, exclude anything you distrust, and approve a version.</li>
          </ol>
          {meta && <><h3>Sources in use</h3><p className="hint">{meta.sources.map((s) => SOURCE_LABELS[s] ?? s).join(", ")}</p></>}
          <h3>Tips for a good question</h3>
          <ul style={{ paddingLeft: 20 }}>
            <li>Use official gene symbols.</li>
            <li>Compare a few related genes rather than many unrelated ones.</li>
            <li>Set the cutoff to the date your decision depends on.</li>
          </ul>
        </aside>
      </div>
    </>
  );
}
