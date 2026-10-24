"use client";
import { useCallback, useEffect, useState } from "react";

let csrfToken: string | null = null;

async function csrf(): Promise<string> {
  if (csrfToken) return csrfToken;
  const response = await fetch("/api/session", { cache: "no-store" });
  if (!response.ok) throw new ApiError(401, "Your session expired. Please sign in again.");
  csrfToken = (await response.json()).csrf;
  return csrfToken!;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function friendly(status: number, body: any): string {
  const detail = body?.error?.message ?? (Array.isArray(body?.detail) ? body.detail.map((d: any) => d.msg).join("; ") : "");
  if (status === 401) return "Your session expired. Please sign in again.";
  if (status === 403) return detail || "You do not have permission to do that.";
  if (status === 409) return detail || "This changed since you opened it. Reload and try again.";
  return detail || `Request failed (${status}).`;
}

export async function call<T>(method: string, path: string, body?: unknown, headers: Record<string, string> = {}): Promise<T> {
  const init: RequestInit = { method, headers: { ...headers }, cache: "no-store" };
  if (method !== "GET") {
    (init.headers as Record<string, string>)["x-csrf-token"] = await csrf();
    (init.headers as Record<string, string>)["content-type"] = "application/json";
    init.body = JSON.stringify(body ?? {});
  }
  const response = await fetch(`/api/proxy/${path}`, init).catch(() => {
    throw new ApiError(0, "Network error. Check your connection and retry.");
  });
  const text = await response.text();
  const parsed = text ? safeJson(text) : null;
  if (!response.ok) throw new ApiError(response.status, friendly(response.status, parsed));
  return parsed as T;
}

function safeJson(text: string): unknown {
  try { return JSON.parse(text); } catch { return text; }
}

/** Loads data with explicit loading / error / data states (UI-04). */
export function useLoad<T>(path: string | null) {
  const [state, setState] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: !!path });
  const reload = useCallback(() => {
    if (!path) return;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    call<T>("GET", path).then(
      (data) => setState({ data, loading: false }),
      (error: ApiError) => setState({ error: error.message, loading: false }),
    );
  }, [path]);
  useEffect(reload, [reload]);
  return { ...state, reload };
}
