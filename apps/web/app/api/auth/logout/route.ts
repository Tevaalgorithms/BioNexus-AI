import { NextRequest, NextResponse } from "next/server";
import { loadConfig } from "@/lib/config";
import { logoutUrl } from "@/lib/cognito";
import { csrfValid, currentSession, destroy, SESSION_COOKIE } from "@/lib/session";

export async function POST(request: NextRequest) {
  const session = await currentSession();
  const form = await request.formData();
  if (session && !csrfValid(session, String(form.get("csrf") ?? ""))) {
    return new NextResponse("Invalid CSRF token", { status: 403 });
  }
  const config = loadConfig();
  const kind = session?.kind ?? "scientist";
  destroy(session?.id);
  const target = config.authMode === "cognito" ? logoutUrl(config, kind) : new URL(kind === "admin" ? "/admin/login" : "/login", config.baseUrl).toString();
  const response = NextResponse.redirect(target, 303);
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
