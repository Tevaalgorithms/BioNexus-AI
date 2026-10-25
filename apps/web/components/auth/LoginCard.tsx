import { Icon } from "../ui/icons";
import { HeroNetwork, Logo } from "../ui/illustrations";

export default function LoginCard({ kind, returnTo }: { kind: "admin" | "scientist"; returnTo?: string }) {
  const admin = kind === "admin";
  const query = new URLSearchParams({ kind, ...(returnTo ? { returnTo } : {}) }).toString();
  return (
    <div className="login-split">
      <aside className="login-art" aria-label="About BioNexus">
        <div style={{ maxWidth: 520 }}>
          <HeroNetwork />
          <h2 style={{ marginTop: 20 }}>Evidence you can trace, from source to sign-off</h2>
          <p className="lede">Source specialists gather genetic, literature, pathway and trial evidence. AI reviewers challenge and check it. A scientist approves it.</p>
        </div>
      </aside>
      <main className="login-form" id="content">
        <div>
          <div className="brand" style={{ paddingLeft: 0 }}><Logo /> BioNexus AI</div>
          <h1 style={{ margin: "8px 0" }}>{admin ? "Administrator sign-in" : "Scientist sign-in"}</h1>
          <p className="lede">{admin ? "Manage models, the team, sources, spend and audit history for the platform." : "Run evidence investigations and review reports for your research projects."}</p>
          <ul className="trust">
            <li><Icon name="lock" /> Invite-only access: accounts are created by an administrator.</li>
            <li><Icon name="shield" /> {admin ? "Administrators cannot open confidential projects unless they are members." : "Your projects are private to your organisation and its members."}</li>
            <li><Icon name="doc" /> Every result links back to its source passage and records the exact models used.</li>
          </ul>
          <a className="button" href={`/api/auth/login?${query}`} style={{ width: "100%", justifyContent: "center" }}>Continue to secure sign-in</a>
          <p className="hint" style={{ marginTop: 14 }}>{admin ? <>Scientist? <a href="/login">Use the scientist sign-in</a>.</> : <>Administrator? <a href="/admin/login">Use the admin sign-in</a>.</>}</p>
          <p className="hint">Research use only. BioNexus assesses public biomedical evidence; it does not give individual treatment advice.</p>
        </div>
      </main>
    </div>
  );
}
