import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { loadConfig } from "@/lib/config";
import { loadLocal, paramEnv, parseDotenv } from "@/lib/params";

describe("web configuration sources", () => {
  it("parses .env text", () => {
    expect(parseDotenv("# c\nA=1\nB = 'two'\nbad\nC=x=y")).toEqual({ A: "1", B: "two", C: "x=y" });
  });

  it("reads the local .env, letting real environment variables override it", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "bn-"));
    const file = path.join(dir, ".env");
    writeFileSync(file, "SESSION_SECRET=from-file\nOTHER=a\n");
    const values = loadLocal({ BIONEXUS_ENV_FILE: file, OTHER: "b", UNRELATED: "z" } as unknown as NodeJS.ProcessEnv);
    expect(values).toEqual({ SESSION_SECRET: "from-file", OTHER: "b" });
  });

  it("ignores arbitrary process environment in production", () => {
    const env = { APP_ENV: "production", NODE_ENV: "production", COGNITO_DOMAIN: "evil.example" } as unknown as NodeJS.ProcessEnv;
    expect(paramEnv(env).COGNITO_DOMAIN).toBeUndefined();
    expect(paramEnv(env).APP_ENV).toBe("production");
  });

  it("generates a random session secret locally instead of shipping a constant", () => {
    const a = loadConfig({ AUTH_MODE: "dev" } as unknown as NodeJS.ProcessEnv).sessionSecret;
    expect(a.length).toBeGreaterThanOrEqual(32);
    expect(a).not.toMatch(/change-me|dev-only/);
  });
});
