import { describe, expect, it } from "vitest";
import { isSafeProxyPath } from "@/lib/proxy-path";

describe("proxy path safety", () => {
  it("accepts normal API paths", () => {
    expect(isSafeProxyPath(["investigations", "run-abc123", "events", "stream"])).toBe(true);
    expect(isSafeProxyPath(["admin", "models", "claude-haiku-5-5", "smoke-test"])).toBe(true);
    expect(isSafeProxyPath(["projects", "covid-19-host-genes", "members"])).toBe(true);
  });

  it("rejects dot segments, encoded separators, backslashes and empties", () => {
    for (const bad of [
      [".."], ["investigations", "..", "admin", "usage"], ["investigations", "."],
      ["investigations", "..%2fadmin"], ["a/b"], ["a\\b"], ["", "x"], ["x", ""],
      ["investigations", "run id"], ["%2e%2e"], ["x?y=1"], ["x#y"],
    ]) expect(isSafeProxyPath(bad)).toBe(false);
    expect(isSafeProxyPath([])).toBe(false);
  });
});
