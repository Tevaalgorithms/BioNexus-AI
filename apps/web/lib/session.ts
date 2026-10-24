/**
 * Server-side session store. Tokens never reach the browser: the cookie holds an opaque id only
 * (AUTH-08). In-memory is deliberate for the single-host pilot; a restart signs everyone out.
 */
import { cookies } from "next/headers";
import type { LoginKind } from "./config";
import { randomToken } from "./pkce";
import type { TokenSet } from "./cognito";

export const SESSION_COOKIE = "bn_session";
export const IDLE_TIMEOUT_MS = 8 * 60 * 60 * 1000;

export interface User {
  user_id: string;
  role: string;
  tenant_id: string;
  projects: string[];
  client: string;
}

export interface Session {
  id: string;
  kind: LoginKind;
  tokens: TokenSet;
  csrf: string;
  user: User;
  lastSeen: number;
}

const store: Map<string, Session> = ((globalThis as any).__bnSessions ??= new Map());

export function createSession(kind: LoginKind, tokens: TokenSet, user: User): Session {
  const session: Session = { id: randomToken(32), kind, tokens, csrf: randomToken(24), user, lastSeen: Date.now() };
  store.set(session.id, session);
  return session;
}

export function lookup(id: string | undefined, now = Date.now()): Session | null {
  const session = id ? store.get(id) : undefined;
  if (!session) return null;
  if (now - session.lastSeen > IDLE_TIMEOUT_MS) {
    store.delete(session.id);
    return null;
  }
  session.lastSeen = now;
  return session;
}

export function destroy(id: string | undefined): void {
  if (id) store.delete(id);
}

export async function currentSession(): Promise<Session | null> {
  const jar = await cookies();
  return lookup(jar.get(SESSION_COOKIE)?.value);
}

export const sessionCookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const, // Lax so the redirect back from Cognito carries it; CSRF header guards writes
  path: "/",
};

/** Double-submit style check: the header must equal the secret held server-side in the session. */
export function csrfValid(session: Session, header: string | null): boolean {
  return !!header && header === session.csrf;
}
