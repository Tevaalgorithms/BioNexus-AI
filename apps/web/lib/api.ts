import { loadConfig } from "./config";
import { refreshTokens } from "./cognito";
import type { Session } from "./session";

/** Calls the FastAPI backend with the session's access token, refreshing once if it expired. */
export async function backendFetch(session: Session, path: string, init: RequestInit = {}): Promise<Response> {
  const config = loadConfig();
  await ensureFresh(session);
  const send = () =>
    fetch(`${config.apiUrl}${path}`, {
      ...init,
      headers: { ...(init.headers as Record<string, string>), Authorization: `Bearer ${session.tokens.accessToken}` },
      cache: "no-store",
    });
  const response = await send();
  if (response.status !== 401 || !session.tokens.refreshToken) return response;
  await forceRefresh(session);
  return send();
}

async function ensureFresh(session: Session): Promise<void> {
  const expiresSoon = session.tokens.expiresAt - Date.now() < 60_000;
  if (expiresSoon && session.tokens.refreshToken && loadConfig().authMode === "cognito") await forceRefresh(session);
}

async function forceRefresh(session: Session): Promise<void> {
  if (loadConfig().authMode !== "cognito" || !session.tokens.refreshToken) return;
  session.tokens = await refreshTokens(loadConfig(), session.kind, session.tokens.refreshToken);
}

export async function backendJson<T>(session: Session, path: string): Promise<T> {
  const response = await backendFetch(session, path);
  if (!response.ok) throw new Error(`API ${path} returned ${response.status}`);
  return response.json() as Promise<T>;
}
