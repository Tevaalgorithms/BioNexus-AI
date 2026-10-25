/** Inline SVG illustrations. They use theme variables, so they follow light and dark mode. */

/** Hexagon (a ring in a molecule) at a given centre. */
const hex = (cx: number, cy: number, r: number) =>
  Array.from({ length: 6 }, (_, i) => `${cx + r * Math.cos((Math.PI / 3) * i - Math.PI / 6)},${cy + r * Math.sin((Math.PI / 3) * i - Math.PI / 6)}`).join(" ");

export function HeroNetwork({ title = "Evidence from four kinds of source flows to a team of specialists and AI reviewers, then to a report a scientist approves" }: { title?: string }) {
  const sources = [["Genetics", 54, "dna"], ["Literature", 128, "book"], ["Pathways", 202, "path"], ["Clinical", 276, "flask"]] as const;
  return (
    <svg viewBox="0 0 560 360" role="img" aria-label={title} style={{ width: "100%", height: "auto" }}>
      <defs>
        <pattern id="hn-dots" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1" fill="var(--border-strong)" opacity=".55" /></pattern>
        <marker id="hn-a" markerWidth="8" markerHeight="8" refX="6.500" refY="4" orient="auto"><path d="M0 0L8 4L0 8z" fill="var(--brand)" /></marker>
      </defs>
      <rect x="1" y="1" width="558" height="358" rx="12" fill="var(--surface)" stroke="var(--border)" />
      <rect x="1" y="1" width="558" height="358" rx="12" fill="url(#hn-dots)" />
      {sources.map(([label, y]) => (
        <g key={label}>
          <path d={`M146 ${y + 20} H190 V180 H224`} fill="none" stroke="var(--border-strong)" strokeWidth="2" />
          <rect x="30" y={y} width="116" height="40" rx="6" fill="var(--surface)" stroke="var(--border-strong)" />
          <rect x="30" y={y} width="5" height="40" rx="2" fill="var(--brand-2)" />
          <text x="92" y={y + 25} textAnchor="middle" fontSize="13" fontWeight="650" fill="var(--text)">{label}</text>
        </g>
      ))}
      <polygon points={hex(262, 180, 44)} fill="var(--brand)" />
      <polygon points={hex(262, 180, 56)} fill="none" stroke="var(--brand)" strokeOpacity=".35" strokeWidth="2" />
      <text x="262" y="177" textAnchor="middle" fontSize="12" fontWeight="700" fill="var(--on-brand)">Evidence</text>
      <text x="262" y="193" textAnchor="middle" fontSize="12" fontWeight="700" fill="var(--on-brand)">team</text>
      <path d="M322 180 H382" stroke="var(--brand)" strokeWidth="2.500" markerEnd="url(#hn-a)" />
      <g transform="translate(386 112)">
        <rect width="150" height="136" rx="8" fill="var(--surface)" stroke="var(--border-strong)" strokeWidth="1.500" />
        <rect width="150" height="26" rx="8" fill="var(--surface-2)" /><rect y="18" width="150" height="8" fill="var(--surface-2)" />
        <circle cx="14" cy="13" r="3.500" fill="var(--opposes)" /><circle cx="26" cy="13" r="3.500" fill="var(--warn)" /><circle cx="38" cy="13" r="3.500" fill="var(--ok)" />
        <text x="14" y="52" fontSize="11" fontWeight="700" fill="var(--text)">Evidence report</text>
        {[["NOD2", 70, 54, 6, 8], ["IL23R", 90, 46, 12, 6]].map(([g, y, a, b, c]) => (
          <g key={g as string}>
            <text x="14" y={(y as number) + 9} fontSize="10" fill="var(--muted)">{g}</text>
            <rect x="52" y={y as number} width={a as number} height="11" rx="2" fill="var(--supports)" />
            <rect x={52 + (a as number) + 2} y={y as number} width={b as number} height="11" rx="2" fill="var(--opposes)" />
            <rect x={52 + (a as number) + (b as number) + 4} y={y as number} width={(c as number) + 12} height="11" rx="2" fill="var(--neutral)" />
          </g>
        ))}
        <line x1="14" y1="112" x2="136" y2="112" stroke="var(--border)" />
        <text x="14" y="127" fontSize="10" fill="var(--muted)">Draft · awaiting approval</text>
      </g>
      <g transform="translate(386 268)">
        <rect width="150" height="40" rx="6" fill="var(--ok-bg)" stroke="var(--ok)" />
        <circle cx="22" cy="20" r="10" fill="var(--ok)" /><path d="M17 20l3.500 3.500 6.500-7" stroke="var(--surface)" strokeWidth="2.500" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <text x="40" y="25" fontSize="11.5" fontWeight="700" fill="var(--ok)">Scientist approves</text>
      </g>
    </svg>
  );
}

export function EmptyIllustration({ label = "Nothing here yet" }: { label?: string }) {
  return (
    <svg viewBox="0 0 220 150" role="img" aria-label={label} style={{ maxWidth: 220, width: "100%" }}>
      <rect x="40" y="18" width="120" height="110" rx="8" fill="var(--surface)" stroke="var(--border-strong)" strokeWidth="1.500" />
      <rect x="40" y="18" width="120" height="22" rx="8" fill="var(--surface-2)" /><rect x="40" y="32" width="120" height="8" fill="var(--surface-2)" />
      <rect x="54" y="56" width="52" height="8" rx="2" fill="var(--brand)" />
      {[76, 92, 108].map((y) => <rect key={y} x="54" y={y} width="92" height="6" rx="2" fill="var(--border)" />)}
      <polygon points={hex(160, 104, 26)} fill="var(--brand-soft)" stroke="var(--brand)" strokeWidth="2.500" />
      <path d="M150 104l7 7 12-14" stroke="var(--brand)" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** A small mark on a role that uses an AI model. */
function AiBadge({ x, y }: { x: number; y: number }) {
  return (
    <g>
      <rect x={x} y={y} width="24" height="14" rx="3" fill="var(--brand)" />
      <text x={x + 12} y={y + 10.500} textAnchor="middle" fontSize="9" fontWeight="700" fill="var(--on-brand)">AI</text>
    </g>
  );
}

/** The team diagram used in "How it works": who does what, left to right. */
export function TeamDiagram() {
  const specialists = [["Genetics", 52], ["Pathways", 130], ["Literature", 208], ["Clinical", 286]] as const;
  const head = (t: string, x: number) => (
    <text key={t} x={x} y="16" textAnchor="middle" fontSize="12" fontWeight="700" letterSpacing=".05em" fill="var(--muted)">{t.toUpperCase()}</text>
  );
  /** The four AI reviewers. Each is a model-assisted role, so each carries the AI mark. */
  const box = (x: number, y: number, title: string, a: string, b: string, tone: "info" | "warn" | "ok" | "brand") => {
    const fill = tone === "brand" ? "var(--brand-soft)" : `var(--${tone}-bg)`;
    const edge = tone === "brand" ? "var(--brand)" : `var(--${tone})`;
    return (
      <g>
        <rect x={x} y={y} width="150" height="76" rx="8" fill={fill} stroke={edge} />
        <AiBadge x={x + 120} y={y + 6} />
        <text x={x + 75} y={y + 28} textAnchor="middle" fontSize="15" fontWeight="700" fill={edge}>{title}</text>
        <text x={x + 75} y={y + 47} textAnchor="middle" fontSize="11" fill="var(--text)">{a}</text>
        <text x={x + 75} y={y + 62} textAnchor="middle" fontSize="11" fill="var(--text)">{b}</text>
      </g>
    );
  };
  return (
    <svg viewBox="0 0 900 340" role="img" style={{ width: "100%", maxWidth: 900, height: "auto", display: "block", margin: "0 auto" }}
      aria-label="Five steps. One: the supervisor plans and starts the genetics, literature and clinical specialists. Two: they gather evidence; genetics can ask pathways for context, but only for genes with genetic support. Three: the planner reviews coverage and the critic reviews conflicts, both AI reviewers; either can ask a specialist to search again, and the critic can ask literature for a passage or a second look. Four: the synthesizer writes cited findings and the verifier checks every claim and summary sentence. Five: a scientist reviews and approves.">
      <defs>
        <marker id="td-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.500" orient="auto-start-reverse"><path d="M0 0L7 3.500L0 7z" fill="var(--muted)" /></marker>
        <marker id="td-arrow-b" markerWidth="7" markerHeight="7" refX="6" refY="3.500" orient="auto-start-reverse"><path d="M0 0L7 3.500L0 7z" fill="var(--brand-2)" /></marker>
      </defs>

      {head("1  Plan", 70)}{head("2  Gather evidence", 245)}{head("3  Review", 475)}{head("4  Write & verify", 675)}{head("5  Approve", 835)}

      {/* supervisor -> the three planned specialists (pathways is asked by genetics, not planned) */}
      <g fill="none" stroke="var(--muted)" strokeWidth="2" strokeLinejoin="round">
        {specialists.filter(([n]) => n !== "Pathways").map(([n, cy]) => <path key={n} d={`M130 169 H150 V${cy} H168`} markerEnd="url(#td-arrow)" />)}
      </g>
      <rect x="10" y="137" width="120" height="64" rx="8" fill="var(--brand)" />
      <text x="70" y="165" textAnchor="middle" fontSize="15" fontWeight="700" fill="var(--on-brand)">Supervisor</text>
      <text x="70" y="184" textAnchor="middle" fontSize="11" fill="var(--on-brand)">assigns the tasks</text>

      {/* specialists */}
      {specialists.map(([n, cy]) => (
        <g key={n}>
          <rect x="170" y={cy - 20} width="150" height="40" rx="6" fill="var(--brand-soft)" stroke="var(--brand)" strokeOpacity=".45" strokeDasharray={n === "Pathways" ? "4 3" : undefined} />
          <text x="245" y={cy + 5} textAnchor="middle" fontSize="14" fontWeight="650" fill="var(--brand)">{n}</text>
          {n === "Literature" && <AiBadge x={292} y={cy - 17} />}
        </g>
      ))}
      {/* genetics asks pathways */}
      <path d="M208 73 V107" stroke="var(--brand-2)" strokeWidth="2.500" fill="none" markerEnd="url(#td-arrow-b)" />
      <text x="220" y="88" fontSize="11" fontWeight="600" fill="var(--brand-2)">asks for context</text>
      <text x="220" y="101" fontSize="10" fill="var(--muted)">supported genes only</text>

      {/* every specialist hands its evidence on */}
      <path d="M320 52 H350 M320 130 H350 M320 208 H350 M320 286 H350 M350 52 V286" stroke="var(--muted)" strokeWidth="2" fill="none" />
      <path d="M350 88 H398" stroke="var(--muted)" strokeWidth="2" fill="none" markerEnd="url(#td-arrow)" />
      <path d="M350 198 H398" stroke="var(--muted)" strokeWidth="2" fill="none" markerEnd="url(#td-arrow)" />

      {/* planner and critic may ask a specialist to search again (request and answer) */}
      <path d="M398 114 H352" stroke="var(--brand-2)" strokeWidth="2.500" fill="none" markerStart="url(#td-arrow-b)" markerEnd="url(#td-arrow-b)" />
      <path d="M398 250 H352" stroke="var(--brand-2)" strokeWidth="2.500" fill="none" markerStart="url(#td-arrow-b)" markerEnd="url(#td-arrow-b)" />

      {box(400, 58, "Planner", "reviews coverage,", "asks for more evidence", "info")}
      <path d="M475 134 V184" stroke="var(--muted)" strokeWidth="2" fill="none" markerEnd="url(#td-arrow)" />
      {box(400, 186, "Critic", "flags and explains conflicts,", "asks for a second look", "warn")}

      {/* critic -> synthesizer -> verifier -> scientist */}
      <path d="M550 224 H575 V96 H598" stroke="var(--muted)" strokeWidth="2" fill="none" strokeLinejoin="round" markerEnd="url(#td-arrow)" />
      {box(600, 58, "Synthesizer", "writes findings citing", "only accepted evidence", "ok")}
      <path d="M675 134 V184" stroke="var(--muted)" strokeWidth="2" fill="none" markerEnd="url(#td-arrow)" />
      {box(600, 186, "Verifier", "checks every claim and", "summary sentence", "brand")}
      <path d="M750 224 H773" stroke="var(--muted)" strokeWidth="2" fill="none" markerEnd="url(#td-arrow)" />
      <rect x="775" y="186" width="120" height="76" rx="8" fill="var(--surface)" stroke="var(--ok)" strokeWidth="2.500" />
      <circle cx="835" cy="212" r="11" fill="var(--ok)" /><path d="M829.500 212l4 4 7-8" stroke="var(--surface)" strokeWidth="2.500" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <text x="835" y="243" textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--text)">Scientist</text>
      <text x="835" y="257" textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--text)">approves</text>

      {/* legend */}
      <path d="M10 322 H40" stroke="var(--muted)" strokeWidth="2" markerEnd="url(#td-arrow)" />
      <text x="48" y="326" fontSize="11" fill="var(--muted)">evidence and results move on</text>
      <path d="M270 322 H300" stroke="var(--brand-2)" strokeWidth="2.500" markerStart="url(#td-arrow-b)" markerEnd="url(#td-arrow-b)" />
      <text x="308" y="326" fontSize="11" fill="var(--muted)">one team member asks another and gets an answer</text>
      <AiBadge x={640} y={315} />
      <text x="670" y="326" fontSize="11" fill="var(--muted)">uses an AI model</text>
    </svg>
  );
}

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <polygon points={hex(16, 16, 14)} fill="var(--logo-bg, var(--brand))" />
      <g stroke="var(--logo-fg, var(--on-brand))" strokeWidth="1.800" strokeLinecap="round" fill="none"><path d="M11 12.500l5 8M21 12l-5 8.500M11.500 12h9" /></g>
      <g fill="var(--logo-fg, var(--on-brand))"><circle cx="11" cy="12.500" r="2.400" /><circle cx="21" cy="12" r="2.400" /><circle cx="16" cy="20.500" r="2.400" /></g>
    </svg>
  );
}
