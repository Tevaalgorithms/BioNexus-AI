import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

const b64url = (buf: Buffer) => buf.toString("base64url");

export const randomToken = (bytes = 32) => b64url(randomBytes(bytes));

export function challengeFor(verifier: string): string {
  return b64url(createHash("sha256").update(verifier).digest());
}

export function newPkce() {
  const verifier = randomToken(48);
  return { verifier, challenge: challengeFor(verifier) };
}

export function sign(value: string, secret: string): string {
  const mac = createHmac("sha256", secret).update(value).digest("base64url");
  return `${Buffer.from(value).toString("base64url")}.${mac}`;
}

/** Returns the original value, or null if the signature does not match. */
export function unsign(signed: string, secret: string): string | null {
  const [payload, mac] = signed.split(".");
  if (!payload || !mac) return null;
  const value = Buffer.from(payload, "base64url").toString();
  const expected = createHmac("sha256", secret).update(value).digest("base64url");
  const a = Buffer.from(mac);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b) ? value : null;
}

/** Only same-site relative paths under the login's own area are honoured (AUTH-03). */
export function safeReturnTo(candidate: string | null, fallback: string, prefix: string): string {
  if (!candidate || !candidate.startsWith(prefix) || candidate.startsWith("//") || candidate.includes("\\")) {
    return fallback;
  }
  return candidate;
}
