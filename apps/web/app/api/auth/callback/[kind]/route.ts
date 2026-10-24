import { NextRequest, NextResponse } from "next/server";
import { HOME, LoginKind, REQUIRED_ROLE, loadConfig } from "@/lib/config";
import { exchangeCode, idTokenNonce } from "@/lib/cognito";
import { unsign } from "@/lib/pkce";
import { createSession, SESSION_COOKIE, sessionCookieOptions, User } from "@/lib/session";

interface LoginState {
  state: string;
  nonce: string;
  verifier: string;
  kind: LoginKind;
  returnTo: string;
}

// Redirects use the public address: behind the proxy, request.url is the container's internal one.
function denied(baseUrl: string, reason: string) {
  const url = new URL("/access-denied", baseUrl);
  url.searchParams.set("reason", reason);
  const response = NextResponse.redirect(url);
  response.cookies.delete("bn_login");
  return response;
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ kind: string }> }) {
  const config = loadConfig();
  const { kind: rawKind } = await params;
  if (rawKind !== "admin" && rawKind !== "scientist") return denied(config.baseUrl, "unknown-login");
  const kind: LoginKind = rawKind;

  const saved = unsign(request.cookies.get("bn_login")?.value ?? "", config.sessionSecret);
  if (!saved) return denied(config.baseUrl, "login-expired");
  const login: LoginState = JSON.parse(saved);

  const url = request.nextUrl.searchParams;
  if (login.kind !== kind || url.get("state") !== login.state || !url.get("code")) {
    return denied(config.baseUrl, "state-mismatch");
  }

  const tokens = await exchangeCode(config, kind, url.get("code")!, login.verifier).catch(() => null);
  if (!tokens || idTokenNonce(tokens.idToken) !== login.nonce) return denied(config.baseUrl, "token-exchange");

  const me = await fetch(`${config.apiUrl}/me`, { headers: { Authorization: `Bearer ${tokens.accessToken}` } });
  if (!me.ok) return denied(config.baseUrl, "no-account");
  const user: User = await me.json();
  if (user.role !== REQUIRED_ROLE[kind]) return denied(config.baseUrl, "wrong-role");

  const session = createSession(kind, tokens, user);
  const response = NextResponse.redirect(new URL(login.returnTo || HOME[kind], config.baseUrl));
  response.cookies.set(SESSION_COOKIE, session.id, sessionCookieOptions);
  response.cookies.delete("bn_login");
  return response;
}
