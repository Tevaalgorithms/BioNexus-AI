import type { LoginKind, WebConfig } from "./config";
import { callbackUrl } from "./config";

export interface TokenSet {
  accessToken: string;
  refreshToken?: string;
  idToken?: string;
  expiresAt: number; // epoch ms
}

export function authorizeUrl(
  config: WebConfig,
  kind: LoginKind,
  params: { state: string; nonce: string; challenge: string },
): string {
  const url = new URL(`https://${config.cognitoDomain}/oauth2/authorize`);
  url.search = new URLSearchParams({
    response_type: "code",
    client_id: config.clients[kind].clientId,
    redirect_uri: callbackUrl(config, kind),
    scope: "openid",
    state: params.state,
    nonce: params.nonce,
    code_challenge: params.challenge,
    code_challenge_method: "S256",
  }).toString();
  return url.toString();
}

async function tokenRequest(config: WebConfig, kind: LoginKind, form: Record<string, string>): Promise<TokenSet> {
  const { clientId, clientSecret } = config.clients[kind];
  const basic = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");
  const response = await fetch(`https://${config.cognitoDomain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", Authorization: `Basic ${basic}` },
    body: new URLSearchParams({ client_id: clientId, ...form }),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Token endpoint returned ${response.status}`);
  const body = await response.json();
  return {
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    idToken: body.id_token,
    expiresAt: Date.now() + (body.expires_in ?? 3600) * 1000,
  };
}

export function exchangeCode(config: WebConfig, kind: LoginKind, code: string, verifier: string) {
  return tokenRequest(config, kind, {
    grant_type: "authorization_code",
    code,
    code_verifier: verifier,
    redirect_uri: callbackUrl(config, kind),
  });
}

export async function refreshTokens(config: WebConfig, kind: LoginKind, refreshToken: string) {
  const tokens = await tokenRequest(config, kind, { grant_type: "refresh_token", refresh_token: refreshToken });
  return { ...tokens, refreshToken: tokens.refreshToken ?? refreshToken };
}

/** Reads the nonce from the ID token returned over the TLS-protected token endpoint. */
export function idTokenNonce(idToken: string | undefined): string | null {
  if (!idToken) return null;
  const payload = idToken.split(".")[1];
  if (!payload) return null;
  try {
    return JSON.parse(Buffer.from(payload, "base64url").toString()).nonce ?? null;
  } catch {
    return null;
  }
}

export function logoutUrl(config: WebConfig, kind: LoginKind): string {
  const url = new URL(`https://${config.cognitoDomain}/logout`);
  url.search = new URLSearchParams({
    client_id: config.clients[kind].clientId,
    logout_uri: `${config.baseUrl}/${kind === "admin" ? "admin/login" : "login"}`,
  }).toString();
  return url.toString();
}
