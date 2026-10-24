import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/api";
import { isSafeProxyPath } from "@/lib/proxy-path";
import { csrfValid, currentSession } from "@/lib/session";

/** Same-origin gateway to the API. The browser never sees or sends a bearer token. */
async function forward(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const session = await currentSession();
  if (!session) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });

  const { path } = await params;
  if (!isSafeProxyPath(path)) return NextResponse.json({ error: "invalid path" }, { status: 400 });
  const isRead = request.method === "GET" || request.method === "HEAD";
  if (!isRead && !csrfValid(session, request.headers.get("x-csrf-token"))) {
    return NextResponse.json({ error: "invalid csrf token" }, { status: 403 });
  }
  if (path[0] === "admin" && session.kind !== "admin") {
    return NextResponse.json({ error: "admin sign-in required" }, { status: 403 });
  }

  const headers: Record<string, string> = {};
  for (const name of ["content-type", "idempotency-key", "last-event-id"]) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
  const upstream = await backendFetch(session, `/${path.join("/")}${request.nextUrl.search}`, {
    method: request.method,
    headers,
    body: isRead ? undefined : await request.text(),
  });
  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "cache-control": "no-store",
      "x-accel-buffering": "no",
    },
  });
}

export { forward as GET, forward as POST, forward as PUT };
