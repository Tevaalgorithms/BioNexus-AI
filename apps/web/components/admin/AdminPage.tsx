"use client";
import { useLoad } from "../../hooks/useApi";
import { ErrorNotice, Loading } from "../ui/Async";
import { PageHeader } from "../ui/primitives";

/** The shared frame of every admin screen: title, loading and error states, then the loaded data. */
export function AdminPage<T>({ path, title, subtitle, children }: { path: string; title: string; subtitle?: string; children: (data: T, reload: () => void) => React.ReactNode }) {
  const { data, error, loading, reload } = useLoad<T>(path);
  return (
    <>
      <PageHeader title={title} subtitle={subtitle} />
      {loading && !data && <Loading />}
      {error && <ErrorNotice message={error} onRetry={reload} />}
      {data && children(data, reload)}
    </>
  );
}
