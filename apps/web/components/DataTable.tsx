"use client";
import { ReactNode, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number;
  filterText?: (row: T) => string;
}

const PAGE_SIZE = 10;

/** Sortable, filterable, paginated; state lives in the URL so it survives navigation (UI-05). */
export default function DataTable<T>({ rows, columns, caption, rowKey }: { rows: T[]; columns: Column<T>[]; caption: string; rowKey: (row: T) => string }) {
  const params = useSearchParams();
  const router = useRouter();
  const path = usePathname();
  const query = params.get("q") ?? "";
  const sort = params.get("sort") ?? "";
  const dir = params.get("dir") === "desc" ? "desc" : "asc";
  const page = Math.max(1, Number(params.get("page") ?? 1));

  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params.toString());
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    router.replace(`${path}?${next.toString()}`);
  };

  const visible = useMemo(() => {
    const needle = query.toLowerCase();
    const filtered = rows.filter((row) => !needle || columns.some((c) => (c.filterText?.(row) ?? "").toLowerCase().includes(needle)));
    const column = columns.find((c) => c.key === sort);
    if (!column?.sortValue) return filtered;
    const value = column.sortValue;
    return [...filtered].sort((a, b) => (value(a) < value(b) ? -1 : value(a) > value(b) ? 1 : 0) * (dir === "desc" ? -1 : 1));
  }, [rows, columns, query, sort, dir]);

  const pages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const shown = visible.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div>
      <label htmlFor="table-filter">Filter {caption.toLowerCase()}</label>
      <input id="table-filter" placeholder="Type to filter by disease, gene or status" value={query} onChange={(e) => update({ q: e.target.value, page: "" })} />
      <div className="table-wrap">
        <table>
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col" aria-sort={sort === c.key ? (dir === "asc" ? "ascending" : "descending") : "none"}>
                  {c.sortValue ? (
                    <button onClick={() => update({ sort: c.key, dir: sort === c.key && dir === "asc" ? "desc" : "asc" })}>{c.header}</button>
                  ) : c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr key={rowKey(row)}>{columns.map((c) => <td key={c.key}>{c.render(row)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {visible.length === 0 && <p role="status">No matching rows.</p>}
      <div className="row" aria-label="Pagination">
        <button className="secondary" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>Previous</button>
        <span>Page {page} of {pages}</span>
        <button className="secondary" disabled={page >= pages} onClick={() => update({ page: String(page + 1) })}>Next</button>
      </div>
    </div>
  );
}
