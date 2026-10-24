import { ReactNode } from "react";

/** Renders the report's own, small Markdown subset as React elements (no raw HTML is ever injected). */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|_[^_]+_|`[^`]+`)/g).filter(Boolean).map((part, i) => {
    if (part.startsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("_") && part.endsWith("_") && part.length > 2) return <em key={i}>{part.slice(1, -1)}</em>;
    if (part.startsWith("`")) return <code key={i}>{part.slice(1, -1)}</code>;
    return part;
  });
}

const isRow = (l: string) => l.trim().startsWith("|");

export default function Markdown({ source }: { source: string }) {
  const lines = source.split("\n");
  const out: ReactNode[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("# ")) out.push(<h1 key={i}>{inline(line.slice(2))}</h1>);
    else if (line.startsWith("## ")) out.push(<h2 key={i}>{inline(line.slice(3))}</h2>);
    else if (isRow(line)) {
      const rows: string[][] = [];
      while (i < lines.length && isRow(lines[i])) {
        if (!/^\|[\s:|-]+\|?$/.test(lines[i].trim())) rows.push(lines[i].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()));
        i++;
      }
      i--;
      out.push(
        <div className="table-wrap" key={i}><table>
          <thead><tr>{rows[0].map((c, k) => <th key={k} scope="col">{inline(c)}</th>)}</tr></thead>
          <tbody>{rows.slice(1).map((r, k) => <tr key={k}>{r.map((c, j) => <td key={j}>{inline(c)}</td>)}</tr>)}</tbody>
        </table></div>,
      );
    } else if (line.startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].startsWith("- ")) items.push(lines[i++].slice(2));
      i--;
      out.push(<ul key={i}>{items.map((t, k) => <li key={k}>{inline(t)}</li>)}</ul>);
    } else if (line.trim()) {
      const para: string[] = [line];
      while (i + 1 < lines.length && lines[i + 1].trim() && !/^(#|\||- )/.test(lines[i + 1])) para.push(lines[++i]);
      out.push(<p key={i}>{para.flatMap((p, k) => [...inline(p), k < para.length - 1 ? <br key={`b${k}`} /> : null])}</p>);
    }
  }
  return <article className="report">{out}</article>;
}
