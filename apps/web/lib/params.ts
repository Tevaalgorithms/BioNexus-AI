/**
 * Configuration source for the web/BFF, mirroring the backend:
 *  - production (APP_ENV=production): AWS SSM Parameter Store under SSM_PATH_PREFIX; process
 *    environment is NOT used for settings;
 *  - otherwise: the repo-root `.env` file, with real environment variables taking precedence.
 */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

type Params = Record<string, string>;
const slot = globalThis as unknown as { __bnParams?: Params };

export function parseDotenv(text: string): Params {
  const values: Params = {};
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const eq = line.indexOf("=");
    if (!line || line.startsWith("#") || eq < 1) continue;
    values[line.slice(0, eq).trim()] = line.slice(eq + 1).trim().replace(/^['"]|['"]$/g, "");
  }
  return values;
}

export function loadLocal(env: NodeJS.ProcessEnv = process.env): Params {
  const file = env.BIONEXUS_ENV_FILE ?? path.resolve(process.cwd(), "../../.env");
  const fromFile = existsSync(file) ? parseDotenv(readFileSync(file, "utf8")) : {};
  const overrides = Object.fromEntries(Object.entries(env).filter(([k, v]) => k in fromFile && v));
  return { ...fromFile, ...(overrides as Params) };
}

export async function loadSsm(prefix: string, region?: string): Promise<Params> {
  const { SSMClient, GetParametersByPathCommand } = await import("@aws-sdk/client-ssm");
  const client = new SSMClient({ region });
  const normalized = prefix.endsWith("/") ? prefix : `${prefix}/`;
  const values: Params = {};
  let token: string | undefined;
  do {
    const page = await client.send(
      new GetParametersByPathCommand({ Path: normalized, Recursive: true, WithDecryption: true, NextToken: token }),
    );
    for (const p of page.Parameters ?? []) values[p.Name!.slice(normalized.length).replaceAll("/", "_")] = p.Value ?? "";
    token = page.NextToken;
  } while (token);
  return values;
}

export async function loadParams(env: NodeJS.ProcessEnv = process.env): Promise<void> {
  slot.__bnParams =
    env.APP_ENV === "production"
      ? await loadSsm(env.SSM_PATH_PREFIX ?? "/bionexus/prod/", env.AWS_REGION)
      : loadLocal(env);
}

/** The environment-like view the rest of the app reads. */
export function paramEnv(env: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  const loaded = slot.__bnParams ?? {};
  const bootstrap = { NODE_ENV: env.NODE_ENV, APP_ENV: env.APP_ENV, ALLOW_DEV_AUTH: env.ALLOW_DEV_AUTH };
  const base = env.APP_ENV === "production" ? bootstrap : env;
  return { ...base, ...loaded } as NodeJS.ProcessEnv;
}
