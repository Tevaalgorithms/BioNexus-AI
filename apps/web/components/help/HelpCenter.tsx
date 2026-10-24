import { Fragment } from "react";
import { AGENTS, GLOSSARY, STAGES } from "@/lib/explain";
import { Icon } from "../ui/icons";
import { TeamDiagram } from "../ui/illustrations";
import { Callout, PageHeader } from "../ui/primitives";

export default function HelpCenter({ audience }: { audience: "scientist" | "admin" }) {
  return (
    <>
      <PageHeader title="How BioNexus works" subtitle="A plain-language guide to what happens when you ask a question, who does what, and how to read the results." />
      <section className="card" aria-labelledby="team-h">
        <div>
          <h2 id="team-h">A team of specialist agents, not one black box</h2>
          <p>Each agent has one job, its own approved data sources and its own configurable AI model. They can only talk to each other through a recorded, rule-checked channel, so you can always see who asked whom for what.</p>
          <ul style={{ paddingLeft: 20 }}>{AGENTS.map((a) => <li key={a.id}><strong>{a.name}:</strong> {a.role}</li>)}</ul>
        </div>
        <div style={{ marginTop: 18 }}><TeamDiagram /></div>
      </section>
      <section className="card" aria-labelledby="steps-h">
        <h2 id="steps-h">The eight steps of every investigation</h2>
        <div className="how">
          {STAGES.map((s, i) => (
            <div className="tile" key={s.id}><div className="num">{i + 1}</div><strong><Icon name={s.icon} size={16} /> {s.label}</strong><p className="hint">{s.plain}</p></div>
          ))}
        </div>
      </section>
      <Callout tone="warn" title="What BioNexus does not do">
        It assembles and assesses public biomedical evidence. It does not prove a disease mechanism, recommend a treatment for a person, or accept patient records. Scores and counts are aids for your judgement, never probabilities.
      </Callout>
      <section className="card" aria-labelledby="gloss-h">
        <h2 id="gloss-h">Glossary</h2>
        <dl className="facts">{GLOSSARY.map((g) => (<Fragment key={g.term}><dt><strong>{g.term}</strong></dt><dd>{g.meaning}</dd></Fragment>))}</dl>
      </section>
      {audience === "admin" ? (
        <section className="card"><h2>For administrators</h2>
          <ul style={{ paddingLeft: 20 }}>
            <li><strong>Changing a model:</strong> Agents &amp; models → Change → Validate → Evaluate on fixtures → Activate (with a reason). It applies to <em>new</em> runs only.</li>
            <li><strong>Adding a model:</strong> Model registry → Add model. It must pass a smoke test, have an API key stored in the parameter store and a dated price.</li>
            <li><strong>Emergency stop:</strong> Overview → Stop all model calls. Running investigations end as incomplete; nothing is silently rerouted.</li>
            <li><strong>Privacy:</strong> administrators manage the platform but cannot open confidential projects without being a member.</li>
          </ul></section>
      ) : (
        <section className="card"><h2>Reviewing a result</h2>
          <ol style={{ paddingLeft: 20 }}>
            <li>Read the progress and any <em>limitations</em>: gaps are listed, not hidden.</li>
            <li>Check the evidence chart and open the cards behind each claim.</li>
            <li>Exclude anything you do not trust (give a reason). A new draft version is created.</li>
            <li>Approve the exact version you reviewed. Only then is it marked approved.</li>
          </ol></section>
      )}
    </>
  );
}
