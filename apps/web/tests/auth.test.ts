import { describe, expect, it, vi } from "vitest";
import { authorizeUrl, idTokenNonce } from "@/lib/cognito";
import { callbackUrl, loadConfig } from "@/lib/config";
import { challengeFor, newPkce, safeReturnTo, sign, unsign } from "@/lib/pkce";

vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => undefined }) }));

const cognitoEnv = {
  AUTH_MODE: "cognito", COGNITO_DOMAIN: "auth.example.com", SESSION_SECRET: "s".repeat(40),
  COGNITO_ADMIN_CLIENT_ID: "admin-id", COGNITO_ADMIN_CLIENT_SECRET: "a",
  COGNITO_SCIENTIST_CLIENT_ID: "sci-id", COGNITO_SCIENTIST_CLIENT_SECRET: "b",
  PUBLIC_BASE_URL: "https://bionexus.example.com",
} as unknown as NodeJS.ProcessEnv;

describe("PKCE and signed state", () => {
  it("derives the S256 challenge from the verifier", () => {
    const { verifier, challenge } = newPkce();
    expect(challenge).toBe(challengeFor(verifier));
    expect(challenge).not.toContain("=");
  });

  it("rejects tampered or foreign-signed login state", () => {
    const signed = sign('{"state":"x"}', "secret-one");
    expect(unsign(signed, "secret-one")).toBe('{"state":"x"}');
    expect(unsign(signed, "secret-two")).toBeNull();
    expect(unsign(signed.replace(/^./, "Z"), "secret-one")).toBeNull();
    expect(unsign("garbage", "secret-one")).toBeNull();
  });
});

describe("return URLs", () => {
  it("only honours relative paths inside the login's own area", () => {
    expect(safeReturnTo("/app/runs/1", "/app", "/app")).toBe("/app/runs/1");
    for (const bad of ["https://evil.com", "//evil.com", "/admin", "/app\\..\\x", null]) {
      expect(safeReturnTo(bad, "/app", "/app")).toBe("/app");
    }
  });
});

describe("Cognito wiring", () => {
  it("uses a separate client and exact callback per login", () => {
    const config = loadConfig(cognitoEnv);
    const admin = new URL(authorizeUrl(config, "admin", { state: "s", nonce: "n", challenge: "c" }));
    const sci = new URL(authorizeUrl(config, "scientist", { state: "s", nonce: "n", challenge: "c" }));
    expect(admin.searchParams.get("client_id")).toBe("admin-id");
    expect(sci.searchParams.get("client_id")).toBe("sci-id");
    expect(admin.searchParams.get("redirect_uri")).toBe("https://bionexus.example.com/api/auth/callback/admin");
    expect(callbackUrl(config, "scientist")).toBe("https://bionexus.example.com/api/auth/callback/scientist");
    expect(admin.searchParams.get("code_challenge_method")).toBe("S256");
    expect(admin.searchParams.get("scope")).toBe("openid");
  });

  it("fails fast when Cognito settings are missing", () => {
    expect(() => loadConfig({ AUTH_MODE: "cognito" } as unknown as NodeJS.ProcessEnv)).toThrow(/COGNITO|SESSION/);
  });

  it("refuses dev authentication in production", () => {
    expect(() => loadConfig({ NODE_ENV: "production" } as unknown as NodeJS.ProcessEnv)).toThrow(/not allowed in production/);
  });

  it("reads the nonce from an ID token", () => {
    const payload = Buffer.from(JSON.stringify({ nonce: "abc" })).toString("base64url");
    expect(idTokenNonce(`h.${payload}.s`)).toBe("abc");
    expect(idTokenNonce("broken")).toBeNull();
    expect(idTokenNonce(undefined)).toBeNull();
  });
});
