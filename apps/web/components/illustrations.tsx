/** Inline SVG illustrations. They use theme variables, so they follow light and dark mode. */

/** Hexagon (a ring in a molecule) at a given centre. */
const hex = (cx: number, cy: number, r: number) =>
  Array.from({ length: 6 }, (_, i) => `${cx + r * Math.cos((Math.PI / 3) * i - Math.PI / 6)},${cy + r * Math.sin((Math.PI / 3) * i - Math.PI / 6)}`).join(" ");

export function HeroNetwork({ title = "Evidence from four kinds of source flows to an agent team, then to a report a scientist approves" }: { title?: string }) {
  const sources = [["Genetics", 54, "dna"], ["Literature", 128, "book"], ["Pathways", 202, "path"], ["Trials", 276, "flask"]] as const;
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
      <text x="262" y="177" textAnchor="middle" fontSize="12" fontWeight="700" fill="var(--on-brand)">Agent</text>
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

/** The team diagram used in "How it works": who does what, left to right. */
export function TeamDiagram() {
  const specialists = [["Genetics", 52], ["Pathways", 130], ["Literature", 208], ["Clinical", 286]] as const;
  return (
    <svg viewBox="0 0 760 336" role="img" style={{ width: "100%", maxWidth: 860, height: "auto", display: "block", margin: "0 auto" }}
      aria-label="Four steps. One: the supervisor plans. Two: genetics, pathways, literature and clinical specialists gather evidence; genetics can ask pathways for context. Three: the critic challenges weak evidence and asks specialists to repair it, then the synthesizer writes cited findings. Four: a scientist reviews and approves.">
      <defs>
        <marker id="td-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.500" orient="auto-start-reverse"><path d="M0 0L7 3.500L0 7z" fill="var(--muted)" /></marker>
        <marker id="td-arrow-b" markerWidth="7" markerHeight="7" refX="6" refY="3.500" orient="auto"><path d="M0 0L7 3.500L0 7z" fill="var(--brand-2)" /></marker>
      </defs>

      {[["1  Plan", 70], ["2  Gather evidence", 265], ["3  Challenge & write", 475], ["4  Approve", 682]].map(([t, x]) => (
        <text key={t as string} x={x as number} y="16" textAnchor="middle" fontSize="12" fontWeight="700" letterSpacing=".05em" fill="var(--muted)">{(t as string).toUpperCase()}</text>
      ))}

      {/* supervisor -> specialists */}
      <g fill="none" stroke="var(--muted)" strokeWidth="2" strokeLinejoin="round">
        {specialists.map(([n, cy]) => <path key={n} d={`M130 169 H160 V${cy} H186`} markerEnd="url(#td-arrow)" />)}
      </g>
      <rect x="10" y="137" width="120" height="64" rx="8" fill="var(--brand)" />
      <text x="70" y="165" textAnchor="middle" fontSize="15" fontWeight="700" fill="var(--on-brand)">Supervisor</text>
      <text x="70" y="184" textAnchor="middle" fontSize="11" fill="var(--on-brand)">assigns the tasks</text>

      {/* specialists */}
      {specialists.map(([n, cy]) => (
        <g key={n}>
          <rect x="190" y={cy - 20} width="150" height="40" rx="6" fill="var(--brand-soft)" stroke="var(--brand)" strokeOpacity=".45" />
          <text x="265" y={cy + 5} textAnchor="middle" fontSize="14" fontWeight="650" fill="var(--brand)">{n}</text>
        </g>
      ))}
      {/* genetics asks pathways */}
      <path d="M228 73 V107" stroke="var(--brand-2)" strokeWidth="2.500" fill="none" markerEnd="url(#td-arrow-b)" />
      <text x="240" y="95" fontSize="11" fontWeight="600" fill="var(--brand-2)">asks for context</text>

      {/* specialists <-> critic (two-way: challenge and repair) */}
      <path d="M340 52 H366 M340 130 H366 M340 208 H366 M340 286 H366 M366 52 V286" stroke="var(--muted)" strokeWidth="2" fill="none" />
      <path d="M366 118 H398" stroke="var(--muted)" strokeWidth="2" fill="none" markerStart="url(#td-arrow)" markerEnd="url(#td-arrow)" />

      {/* critic */}
      <rect x="400" y="80" width="150" height="76" rx="8" fill="var(--warn-bg)" stroke="var(--warn)" />
      <text x="475" y="108" textAnchor="middle" fontSize="15" fontWeight="700" fill="var(--warn)">Critic</text>
      <text x="475" y="127" textAnchor="middle" fontSize="11" fill="var(--text)">challenges weak evidence,</text>
      <text x="475" y="142" textAnchor="middle" fontSize="11" fill="var(--text)">specialists repair it</text>

      {/* critic -> synthesizer -> scientist */}
      <path d="M475 156 V212" stroke="var(--muted)" strokeWidth="2" fill="none" markerEnd="url(#td-arrow)" />
      <rect x="400" y="214" width="150" height="76" rx="8" fill="var(--ok-bg)" stroke="var(--ok)" />
      <text x="475" y="242" textAnchor="middle" fontSize="15" fontWeight="700" fill="var(--ok)">Synthesizer</text>
      <text x="475" y="261" textAnchor="middle" fontSize="11" fill="var(--text)">writes findings citing</text>
      <text x="475" y="276" textAnchor="middle" fontSize="11" fill="var(--text)">only accepted evidence</text>

      <path d="M550 252 H610" stroke="var(--muted)" strokeWidth="2" fill="none" markerEnd="url(#td-arrow)" />
      <rect x="612" y="214" width="140" height="76" rx="8" fill="var(--surface)" stroke="var(--ok)" strokeWidth="2.500" />
      <circle cx="682" cy="240" r="12" fill="var(--ok)" /><path d="M676.500 240l4 4 7-8" stroke="var(--surface)" strokeWidth="2.500" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <text x="682" y="272" textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--text)">Scientist approves</text>
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
