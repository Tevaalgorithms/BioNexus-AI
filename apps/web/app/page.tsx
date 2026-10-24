import { Icon } from "@/components/icons";
import { HeroNetwork, Logo, TeamDiagram } from "@/components/illustrations";
import { STAGES } from "@/lib/explain";

const PHASES = [
  { icon: "alert", title: "Unmet need", text: "A disease without a good treatment", helps: false },
  { icon: "dna", title: "Find the genes", text: "Which genes and proteins are involved?", helps: true },
  { icon: "compass", title: "Choose a target", text: "Pick the most promising one", helps: true },
  { icon: "flask", title: "Lab studies", text: "Test it in cells and animals", helps: false },
  { icon: "user", title: "Clinical trials", text: "Test it in people", helps: false },
  { icon: "check", title: "A medicine", text: "Approved for patients", helps: false },
] as const;

const DECISION_RISKS = [
  { icon: "flask", title: "Time lost on weak leads", text: "Lots of database hits can make a target look well supported when only a few studies truly back it." },
  { icon: "link", title: "No clear source", text: "When someone asks where a claim came from, nobody can quickly show it." },
  { icon: "alert", title: "Problems found too late", text: "Conflicting or missing evidence is easy to miss, and costly to find after the decision." },
] as const;

export default function Home() {
  return (
    <>
      <a className="skip" href="#content">Skip to content</a>
      <header className="topbar">
        <div className="brand"><Logo size={44} /> BioNexus AI</div>
        <div className="row"><a href="/login">Scientist sign-in</a><a className="button secondary" href="/admin/login">Admin sign-in</a></div>
      </header>
      <main id="content">
        <section className="hero">
          <div>
            <p className="eyebrow">Accelerating scientific discovery to bring life-changing treatments closer to patients</p>
            <h1>Helping Scientists Choose Better Drug Targets, Faster</h1>
            <p className="lede">Developing new medicines starts with understanding what causes a disease and where treatments might work. Choosing the wrong direction can cost years of research.</p>
            <p className="lede" style={{ marginTop: 12 }}>BioNexus AI helps scientists make better decisions, faster by bringing together genetic evidence, scientific studies, and clinical trial data to identify promising opportunities, uncover risks, and focus research on treatments that could improve and save lives.</p>
            <div className="row" style={{ marginTop: 22 }}>
              <a className="button" href="/login">Start an investigation</a>
            </div>
          </div>
          <HeroNetwork />
        </section>

        <section className="section" id="purpose">
          <p className="eyebrow">Where BioNexus fits</p>
          <h2>Picking the right target is where every new medicine begins</h2>
          <p className="lede" style={{ fontSize: "1.08rem", maxWidth: "80ch" }}>A target is a gene or protein that plays a part in a disease. Picking the wrong one is a common reason drugs fail in human trials. Clues from people’s own genes are one of the best early signs that a target is the right one, and targets with that support succeed more often.</p>
          <ol className="drugpath" aria-label="From disease to medicine, in six steps">
            <li className="bracket" aria-hidden="true"><span>Where BioNexus helps</span></li>
            {PHASES.map((ph, i) => (
              <li key={ph.title} className={`phase${ph.helps ? " hl" : ""}`} style={{ gridColumn: i + 1, gridRow: 2 }}>
                <div className="node"><Icon name={ph.icon} size={22} /></div>
                <strong>{ph.title}</strong>
                <span>{ph.text}</span>
                {ph.helps && <em className="sr-only">BioNexus helps at this step.</em>}
              </li>
            ))}
          </ol>
        </section>

        <section className="section" style={{ paddingTop: 8 }}>
          <p className="eyebrow">What goes wrong</p>
          <h2>Bad evidence is costly in three ways</h2>
          <div className="grid cols-3" style={{ marginTop: 18 }}>
            {DECISION_RISKS.map((p) => (
              <div className="feature problem" key={p.title}><div className="ico"><Icon name={p.icon} size={22} /></div><h3>{p.title}</h3><p>{p.text}</p></div>
            ))}
          </div>
        </section>

        <section className="section" style={{ paddingTop: 0 }}>
          <div className="statement" role="note">
            BioNexus coordinates a team of specialist AI agents across genetics, literature, pathways and clinical trials. Every claim links to a source passage, contradictions are surfaced rather than hidden, and a scientist signs off.
            <small>In short: faster evidence, with the trust built in.</small>
          </div>
        </section>

        <section className="section">
          <p className="eyebrow">Impact, honestly stated</p>
          <h2>What we have measured, and what a pilot will measure next</h2>
          <div className="grid cols-2" style={{ marginTop: 18 }}>
            <div className="feature"><div className="ico"><Icon name="check" size={22} /></div><h3>Measured so far</h3>
              <ul style={{ margin: 0, paddingLeft: 20, color: "var(--muted)" }}>
                <li>A first sourced draft for two genes in about 20 seconds, from five live databases.</li>
                <li>Repeated studies merged across databases (in a live COVID-19 run, 44 records became 39 distinct studies).</li>
                <li>Every excluded record listed with its reason.</li>
                <li>Every report records the models, skills and data versions behind it.</li>
              </ul></div>
            <div className="feature"><div className="ico"><Icon name="chart" size={22} /></div><h3>Still to be measured in a pilot</h3>
              <ul style={{ margin: 0, paddingLeft: 20, color: "var(--muted)" }}>
                <li>Scientist hours saved compared with a manual search.</li>
                <li>How often it finds all the evidence an expert would, and how often its citations hold up on expert review.</li>
                <li>Whether the multi-agent team beats a simpler single-agent approach at equal cost.</li>
              </ul></div>
          </div>
        </section>

        <section className="band">
          <div className="section">
            <p className="eyebrow">How it works</p>
            <h2>A coordinated team, with every handoff recorded</h2>
            <TeamDiagram />
            <h3 style={{ marginTop: 28 }}>From question to approved report in eight visible steps</h3>
            <div className="how">
              {STAGES.map((s, i) => (
                <div className="tile" key={s.id}><div className="num">{i + 1}</div><strong><Icon name={s.icon} size={16} /> {s.label}</strong><p className="hint">{s.plain}</p></div>
              ))}
            </div>
          </div>
        </section>

        <section className="section">
          <div className="grid cols-2">
            <div className="feature"><div className="ico"><Icon name="user" size={22} /></div><h3>Who it is for</h3>
              <p>Research scientists, translational and target-discovery teams, and reviewers who need a fast, sourced starting point and want to see how a conclusion was reached.</p></div>
            <div className="feature"><div className="ico"><Icon name="lock" size={22} /></div><h3>What it is not</h3>
              <p>A research aid, not a clinical tool. It does not diagnose, recommend treatments for a person, accept patient records, or prove that a gene causes a disease. Counts and scores guide judgement; they are not probabilities.</p></div>
          </div>
        </section>

        <section className="band"><div className="cta-band">
          <p className="eyebrow">Our aim</p>
          <h2>Accelerating scientific discovery to bring new treatments closer to patients</h2>
          <p className="lede" style={{ margin: "0 auto 18px" }}>Sign in, create a project, pick a disease and a few genes, and watch the agent team build a draft you can review.</p>
          <a className="button" href="/login">Start an investigation</a>
        </div></section>
      </main>
    </>
  );
}
