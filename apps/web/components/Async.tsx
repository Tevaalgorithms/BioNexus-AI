import { ReactNode } from "react";

export function Loading({ what = "content" }: { what?: string }) {
  return <p role="status">Loading {what}…</p>;
}

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="notice bad" role="alert">
      {message} {onRetry && <button className="secondary" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="notice">{children}</div>;
}
