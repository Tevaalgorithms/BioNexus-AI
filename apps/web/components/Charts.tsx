import type { MatrixRow } from "@/lib/types";
import { STANCE_HELP, STANCE_LABEL } from "@/lib/explain";

const COLORS: Record<string, string> = { supports: "var(--supports)", opposes: "var(--opposes)", unknown: "var(--neutral)" };

export function StanceLegend() {
  return (
    <div className="legend" aria-label="Legend">
      {(["supports", "opposes", "unknown"] as const).map((s) => (
        <span key={s} title={STANCE_HELP[s]}><i style={{ background: COLORS[s] }} />{STANCE_LABEL[s]}</span>
      ))}
    </div>
  );
}

/**
 * One stacked bar per target: how many independent study families support, oppose or give no
 * direction. Diverging blue/red with a neutral middle; counts are written out, so colour is never the
 * only signal. The table below the chart is the accessible data view.
 */
export function StanceChart({ rows }: { rows: MatrixRow[] }) {
  const max = Math.max(1, ...rows.map((r) => r.supporting_families + r.opposing_families + r.unknown_families));
  return (
    <div role="group" aria-label="Independent study families per target, by direction">
      {rows.map((r) => {
        const parts = [["supports", r.supporting_families], ["opposes", r.opposing_families], ["unknown", r.unknown_families]] as const;
        return (
          <div className="stance-row" key={r.target}>
            <strong>{r.target}</strong>
            <div className="stance-bar" style={{ width: `${((r.supporting_families + r.opposing_families + r.unknown_families) / max) * 100}%` }}>
              {parts.filter(([, n]) => n > 0).map(([k, n]) => (
                <span key={k} style={{ background: COLORS[k], flexGrow: n }} title={`${n} ${STANCE_LABEL[k].toLowerCase()} for ${r.target}`} />
              ))}
            </div>
            <span className="hint" style={{ margin: 0 }}>
              {r.supporting_families} supporting · {r.opposing_families} opposing · {r.unknown_families} no direction
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Single-series horizontal bars with the value written at the end of each bar. */
export function HBars({ data, unit = "$", digits = 4 }: { data: Record<string, number>; unit?: string; digits?: number }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1e-9, ...entries.map(([, v]) => v));
  return (
    <div className="hbars" role="list">
      {entries.map(([k, v]) => (
        <div className="hb" role="listitem" key={k}>
          <span>{k}</span>
          <div className="track" aria-hidden="true"><div className="fill" style={{ width: `${(v / max) * 100}%` }} /></div>
          <span className="num">{unit}{v.toFixed(digits)}</span>
        </div>
      ))}
    </div>
  );
}
