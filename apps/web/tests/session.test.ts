import { describe, expect, it, vi } from "vitest";
import { createSession, csrfValid, destroy, IDLE_TIMEOUT_MS, lookup } from "@/lib/session";

vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => undefined }) }));

const user = { user_id: "u", role: "scientist", tenant_id: "t", projects: ["p"], client: "scientist" };
const tokens = { accessToken: "secret-token", expiresAt: Date.now() + 1000 };

describe("server-side sessions", () => {
  it("returns the session for its opaque id and expires it when idle", () => {
    const session = createSession("scientist", tokens, user);
    expect(lookup(session.id)?.user.user_id).toBe("u");
    expect(lookup(session.id, Date.now() + IDLE_TIMEOUT_MS + 1)).toBeNull();
    expect(lookup(session.id)).toBeNull();
  });

  it("never exposes tokens in the id and can be destroyed", () => {
    const session = createSession("admin", tokens, user);
    expect(session.id).not.toContain("secret-token");
    destroy(session.id);
    expect(lookup(session.id)).toBeNull();
    expect(lookup(undefined)).toBeNull();
  });

  it("validates CSRF only for the exact per-session token", () => {
    const a = createSession("scientist", tokens, user);
    const b = createSession("scientist", tokens, user);
    expect(csrfValid(a, a.csrf)).toBe(true);
    expect(csrfValid(a, b.csrf)).toBe(false);
    expect(csrfValid(a, null)).toBe(false);
    expect(csrfValid(a, "")).toBe(false);
  });
});
