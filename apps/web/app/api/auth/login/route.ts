import { NextRequest, NextResponse } from "next/server";
import { HOME, LoginKind, WebConfig, loadConfig } from "@/lib/config";
import { authorizeUrl } from "@/lib/cognito";
import { paramEnv } from "@/lib/params";
import { newPkce, randomToken, safeReturnTo, sign } from "@/lib/pkce";
import { createSession, SESSION_COOKIE, sessionCookieOptions } from "@/lib/session";

/** Local-only sign-in tokens come from your own `.env`; there are none in the code. */
function devToken(kind: LoginKind): string | undefined {
  return paramEnv()[kind === "admin" ? "DEV_ADMIN_TOKEN" : "DEV_SCIENTIST_TOKEN"];
}

export async function GET(request: NextRequest) {
  const config = loadConfig();
  const kind = request.nextUrl.searchParams.get("kind") === "admin" ? "admin" : "scientist";
  const returnTo = safeReturnTo(request.nextUrl.searchParams.get("returnTo"), HOME[kind], HOME[kind]);

  if (config.authMode === "dev") return devLogin(config, kind, returnTo);

  const { verifier, challenge } = newPkce();
  const state = randomToken(24);
  const nonce = randomToken(24);
  const response = NextResponse.redirect(authorizeUrl(config, kind, { state, nonce, challenge }));
  const cookieValue = sign(JSON.stringify({ state, nonce, verifier, kind, returnTo }), config.sessionSecret);
  response.cookies.set("bn_login", cookieValue, { ...sessionCookieOptions, maxAge: 600 });
  return response;
}

async function devLogin({ apiUrl, baseUrl }: WebConfig, kind: LoginKind, returnTo: string) {
  const token = devToken(kind);
  if (!token) return NextResponse.redirect(new URL("/access-denied?reason=no-account", baseUrl));
  const me = await fetch(`${apiUrl}/me`, { headers: { Authorization: `Bearer ${token}` } });
  if (!me.ok) return NextResponse.redirect(new URL("/access-denied", baseUrl));
  const session = createSession(kind, { accessToken: token, expiresAt: Date.now() + 3_600_000 }, await me.json());
  const response = NextResponse.redirect(new URL(returnTo, baseUrl));
  response.cookies.set(SESSION_COOKIE, session.id, sessionCookieOptions);
  return response;
}
