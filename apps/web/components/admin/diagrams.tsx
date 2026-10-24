import type { Release } from "@/lib/types";
import { SKILL_FOR } from "@/lib/explain";

/** Admin explainer diagrams. Plain SVG using theme variables, so they follow light and dark mode. */

const arrowDefs = (
  <defs>
    <marker id="dg-arrow" markerWidth="8" markerHeight="8" refX="6.500" refY="4" orient="auto"><path d="M0 0L8 4L0 8z" fill="var(--muted)" /></marker>
  </defs>
);

function Box({ x, y, w, h, title, lines = [], tone = "plain" }: { x: number; y: number; w: number; h: number; title: string; lines?: string[]; tone?: "plain" | "brand" | "ok" | "warn" }) {
  const fill = { plain: "var(--surface)", brand: "var(--brand-soft)", ok: "var(--ok-bg)", warn: "var(--warn-bg)" }[tone];
  const stroke = { plain: "var(--border-strong)", brand: "var(--brand)", ok: "var(--ok)", warn: "var(--warn)" }[tone];
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx="8" fill={fill} stroke={stroke} strokeWidth={tone === "plain" ? 1.2 : 1.6} />
      <text x={x + w / 2} y={y + 22} textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--text)">{title}</text>
      {lines.map((l, i) => <text key={l} x={x + w / 2} y={y + 40 + i * 15} textAnchor="middle" fontSize="11" fill="var(--muted)">{l}</text>)}
    </g>
  );
}

const Arrow = ({ x1, y1, x2, y2 }: { x1: number; y1: number; x2: number; y2: number }) => (
  <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--muted)" strokeWidth="2" markerEnd="url(#dg-arrow)" />
);

/** How evidence sources are reached: web APIs through one guarded client, not MCP servers. */
export function SourceFlowDiagram() {
  return (
    <svg viewBox="0 0 800 262" role="img" style={{ width: "100%", maxWidth: 920, height: "auto", display: "block", margin: "0 auto" }}
      aria-label="Agents ask BioNexus source adapters. The adapters send requests through one guarded HTTPS client that only allows listed hosts. The client calls the public web APIs of six databases. These are direct web APIs, not MCP servers.">
      {arrowDefs}
      {[["1  Agents", 80], ["2  Source adapters", 270], ["3  Guarded client", 480], ["4  Public databases", 690]].map(([t, x]) => (
        <text key={t as string} x={x as number} y="16" textAnchor="middle" fontSize="11" fontWeight="700" letterSpacing=".06em" fill="var(--muted)">{(t as string).toUpperCase()}</text>
      ))}
      <Box x={10} y={34} w={140} h={112} title="Agent team" lines={["Genetics · Literature", "Pathways · Clinical", "ask for evidence on", "a gene and a disease"]} tone="brand" />
      <Box x={200} y={34} w={140} h={112} title="BioNexus adapters" lines={["one per source", "turn each reply into", "the same evidence", "record shape"]} />
      <Box x={410} y={34} w={140} h={112} title="Guarded HTTP" lines={["HTTPS only", "host allowlist", "30 s timeout · 2 retries", "2 MB response cap"]} tone="warn" />
      <Box x={620} y={34} w={170} h={112} title="Public web APIs" lines={["Open Targets · GWAS", "Europe PMC · Reactome", "Monarch · ClinicalTrials.gov", "no login, no MCP server"]} tone="ok" />
      <Arrow x1={150} y1={90} x2={198} y2={90} /><Arrow x1={340} y1={90} x2={408} y2={90} /><Arrow x1={550} y1={90} x2={618} y2={90} />
      <rect x="10" y="170" width="780" height="78" rx="8" fill="var(--info-bg)" stroke="var(--info)" />
      <text x="26" y="193" fontSize="12" fontWeight="700" fill="var(--text)">Are these MCP servers? No.</text>
      <text x="26" y="212" fontSize="11.5" fill="var(--muted)">Each source is a BioNexus adapter that calls the provider&apos;s public web API (a URL) directly.</text>
      <text x="26" y="228" fontSize="11.5" fill="var(--muted)">A provider&apos;s own MCP server could later be wrapped behind the same adapter without changing the agents.</text>
      <text x="26" y="244" fontSize="11.5" fill="var(--muted)">Retrieved text is always treated as data, never as instructions.</text>
    </svg>
  );
}

/** From a skill file to a line in the report. */
export function SkillFlowDiagram() {
  const steps = [
    ["Skill file", ["versioned, approved", "instructions · limits", "abstain rule"], "plain"],
    ["Release", ["pins skill@version", "for every new run", "(old runs keep theirs)"], "brand"],
    ["Agent prompt", ["skill instructions", "+ the task", "+ evidence as data"], "plain"],
    ["Gateway", ["approved model only", "budget · fallback", "call ledger"], "warn"],
    ["Checked output", ["citations verified", "blocked language", "removed"], "ok"],
    ["Report record", ["skill fingerprint", "stored in the", "run manifest"], "plain"],
  ] as const;
  const w = 128, gap = 24;
  return (
    <svg viewBox={`0 0 ${steps.length * (w + gap) - gap + 20} 130`} role="img" style={{ width: "100%", maxWidth: 920, height: "auto", display: "block", margin: "0 auto" }}
      aria-label="A skill is a versioned, approved instruction file. A configuration release pins its version. The agent builds its prompt from the skill, the task and evidence treated as data. The model gateway runs an approved model. The output is checked, and the report records the skill fingerprint.">
      {arrowDefs}
      {steps.map(([title, lines, tone], i) => (
        <g key={title}>
          <Box x={10 + i * (w + gap)} y={12} w={w} h={104} title={title} lines={[...lines]} tone={tone} />
          {i < steps.length - 1 && <Arrow x1={10 + i * (w + gap) + w} y1={64} x2={10 + (i + 1) * (w + gap) - 2} y2={64} />}
        </g>
      ))}
    </svg>
  );
}

/** What the active release means: per-agent skill and model, then the gateway and providers. */
export function ConfigFlowDiagram({ release }: { release: Release }) {
  const rows = Object.entries(release.bindings);
  const rowH = 34, top = 28, height = top + rows.length * rowH + 16;
  return (
    <svg viewBox={`0 0 800 ${height}`} role="img" style={{ width: "100%", maxWidth: 920, height: "auto", display: "block", margin: "0 auto" }}
      aria-label={`Release ${release.release_id} sets a skill and a model for each of ${rows.length} agents. Every model call goes through the model gateway, which only allows approved models, applies fallback and budget, and calls the provider.`}>
      {arrowDefs}
      <text x="85" y="16" textAnchor="middle" fontSize="11" fontWeight="700" letterSpacing=".06em" fill="var(--muted)">RELEASE</text>
      <text x="405" y="16" textAnchor="middle" fontSize="11" fontWeight="700" letterSpacing=".06em" fill="var(--muted)">EACH AGENT USES  (SKILL · MODEL ↪ FALLBACK)</text>
      <text x="700" y="16" textAnchor="middle" fontSize="11" fontWeight="700" letterSpacing=".06em" fill="var(--muted)">GATEWAY AND PROVIDERS</text>
      <Box x={10} y={top} w={150} h={rows.length * rowH - 6} title={`Release ${release.release_id}`} lines={[`revision ${release.revision}`, `${rows.length} agent bindings`, `${Object.keys(release.skill_versions).length} skill versions`, "fixed when a run starts", "changes affect new runs"]} tone="brand" />
      {rows.map(([agent, b], i) => {
        const y = top + i * rowH;
        return (
          <g key={agent}>
            <rect x="190" y={y} width="430" height={rowH - 6} rx="6" fill="var(--surface)" stroke="var(--border-strong)" />
            <text x="202" y={y + 18} fontSize="12" fontWeight="700" fill="var(--text)">{agent[0].toUpperCase() + agent.slice(1)}</text>
            <text x="296" y={y + 18} fontSize="10.5" fill="var(--muted)">{SKILL_FOR[agent]}@{release.skill_versions[SKILL_FOR[agent]]}</text>
            <text x="448" y={y + 18} fontSize="10.5" fill="var(--text)">{b.model_id}{b.fallback_model_id ? ` ↪ ${b.fallback_model_id}` : ""}</text>
            <line x1="160" y1={top + (rows.length * rowH - 6) / 2} x2="188" y2={y + (rowH - 6) / 2} stroke="var(--border-strong)" strokeWidth="1.500" />
            <line x1="620" y1={y + (rowH - 6) / 2} x2="640" y2={top + (rows.length * rowH - 6) / 2 - 20} stroke="var(--border-strong)" strokeWidth="1.500" />
          </g>
        );
      })}
      <Box x={640} y={top} w={150} h={100} title="Model gateway" lines={["approved models only", "fallback · budget", "call ledger"]} tone="warn" />
      <Box x={640} y={top + 130} w={150} h={96} title="Providers" lines={["Anthropic · OpenAI", "via LangChain", "demo mode: placeholder", "model, no real calls"]} tone="ok" />
      <path d={`M715 ${top + 100} V${top + 128}`} stroke="var(--muted)" strokeWidth="2" markerEnd="url(#dg-arrow)" fill="none" />
    </svg>
  );
}
