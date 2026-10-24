/** Environment-derived settings. Secrets are read here, on the server, and nowhere else. */
import { randomBytes } from "node:crypto";
import { paramEnv } from "./params";

export type LoginKind = "admin" | "scientist";

export interface ClientCredentials {
  clientId: string;
  clientSecret: string;
}

export interface WebConfig {
  apiUrl: string;
  baseUrl: string;
  authMode: "cognito" | "dev";
  sessionSecret: string;
  cognitoDomain: string;
  clients: Record<LoginKind, ClientCredentials>;
}

/** A per-process random value, used only when local development has no SESSION_SECRET. */
const ephemeralSecret = randomBytes(32).toString("hex");

function required(name: string, env: NodeJS.ProcessEnv): string {
  const value = env[name];
  if (!value) throw new Error(`Missing required environment variable ${name}`);
  return value;
}

export function loadConfig(env: NodeJS.ProcessEnv = paramEnv()): WebConfig {
  const authMode = env.AUTH_MODE === "cognito" ? "cognito" : "dev";
  if (authMode === "dev" && env.NODE_ENV === "production" && env.ALLOW_DEV_AUTH !== "1") {
    throw new Error("AUTH_MODE=dev is not allowed in production");
  }
  const get = (name: string) => (authMode === "cognito" ? required(name, env) : (env[name] ?? ""));
  return {
    apiUrl: env.BIONEXUS_API_URL ?? "http://localhost:8000",
    baseUrl: env.PUBLIC_BASE_URL ?? "http://localhost:3000",
    authMode,
    sessionSecret: authMode === "dev" ? (env.SESSION_SECRET ?? ephemeralSecret) : required("SESSION_SECRET", env),
    cognitoDomain: get("COGNITO_DOMAIN"),
    clients: {
      admin: { clientId: get("COGNITO_ADMIN_CLIENT_ID"), clientSecret: get("COGNITO_ADMIN_CLIENT_SECRET") },
      scientist: { clientId: get("COGNITO_SCIENTIST_CLIENT_ID"), clientSecret: get("COGNITO_SCIENTIST_CLIENT_SECRET") },
    },
  };
}

/** Each login has its own callback so redirect allowlists stay exact (AUTH-02/03). */
export function callbackUrl(config: WebConfig, kind: LoginKind): string {
  return `${config.baseUrl}/api/auth/callback/${kind}`;
}

/** Landing page per login: /admin for admins, /app for scientists (AUTH-07). */
export const HOME: Record<LoginKind, string> = { admin: "/admin", scientist: "/app" };

export const REQUIRED_ROLE: Record<LoginKind, string> = {
  admin: "platform_admin",
  scientist: "scientist",
};
