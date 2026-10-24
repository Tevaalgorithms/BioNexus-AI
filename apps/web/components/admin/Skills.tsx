"use client";
import { useState } from "react";
import { AdminPage } from "./AdminPage";
import { SkillFlowDiagram } from "./diagrams";
import { Callout } from "../ui/primitives";

interface SkillRow { skill_id: string; version: string; owner: string; approved: boolean; instructions: string; interpretation_limits: string; abstain_when: string; content_hash: string }
interface SkillsPayload { versions: Record<string, string>; hashes: Record<string, string>; skills: SkillRow[] }

function CopyHash({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <span className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
      <code title={value}>{value.slice(0, 12)}…</code>
      <button className="ghost" aria-label={`Copy fingerprint ${value}`} onClick={() => navigator.clipboard?.writeText(value).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}>
        {copied ? "Copied" : "Copy"}
      </button>
    </span>
  );
}

export function Skills() {
  return (
    <AdminPage<SkillsPayload> path="admin/skills" title="Skills" subtitle="Approved, versioned instructions that tell each agent how to do its job and when to stop.">
      {(d) => (
        <>
          <Callout tone="info" title="What a skill is">
            A skill is the written job description for one agent: what to do, what it must not conclude, and when to answer &quot;I don&apos;t know&quot;. Each is approved, versioned and fingerprinted. The active configuration release pins the exact version, so a past report can always show the text its agents followed. An agent cannot edit its own skill or widen its own permissions.
          </Callout>
          <section className="card" aria-labelledby="skill-flow-h">
            <h2 id="skill-flow-h">How a skill is used in a run</h2>
            <SkillFlowDiagram />
          </section>
          <div className="table-wrap"><table>
            <caption className="sr-only">Active skills</caption>
            <thead><tr><th>Skill</th><th>Agent</th><th>Version</th><th>Status</th><th>Fingerprint</th><th>Instructions</th></tr></thead>
            <tbody>{d.skills.map((s) => (
              <tr key={s.skill_id}>
                <th scope="row"><code>{s.skill_id}</code></th>
                <td>{s.owner}</td><td>{s.version}</td>
                <td><span className={`badge ${s.approved ? "ok" : "warn"}`}>{s.approved ? "Approved" : "Not approved"}</span></td>
                <td><CopyHash value={s.content_hash} /></td>
                <td>
                  <details><summary>View</summary>
                    <p><strong>Instructions:</strong> {s.instructions}</p>
                    <p><strong>Limits:</strong> {s.interpretation_limits}</p>
                    <p><strong>Abstains when:</strong> {s.abstain_when}</p>
                  </details>
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        </>
      )}
    </AdminPage>
  );
}
