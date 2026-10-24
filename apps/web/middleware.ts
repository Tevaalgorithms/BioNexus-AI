import { NextRequest, NextResponse } from "next/server";

/** The address the browser used. Behind the proxy, request.url is the container's internal one. */
function publicOrigin(request: NextRequest): string {
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  const proto = request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(":", "");
  return host ? `${proto}://${host}` : request.url;
}

/** Cheap gate: no session cookie means redirect to the right login. Pages still verify server-side. */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isAdminArea = pathname.startsWith("/admin") && pathname !== "/admin/login";
  const isScientistArea = pathname.startsWith("/app");
  if (!(isAdminArea || isScientistArea) || request.cookies.has("bn_session")) return NextResponse.next();
  const login = new URL(isAdminArea ? "/admin/login" : "/login", publicOrigin(request));
  login.searchParams.set("returnTo", pathname);
  return NextResponse.redirect(login);
}

export const config = { matcher: ["/app/:path*", "/admin/:path*"] };
