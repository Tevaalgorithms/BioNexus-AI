import { NextRequest, NextResponse } from "next/server";

/** Cheap gate: no session cookie means redirect to the right login. Pages still verify server-side. */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isAdminArea = pathname.startsWith("/admin") && pathname !== "/admin/login";
  const isScientistArea = pathname.startsWith("/app");
  if (!(isAdminArea || isScientistArea) || request.cookies.has("bn_session")) return NextResponse.next();
  const login = new URL(isAdminArea ? "/admin/login" : "/login", request.url);
  login.searchParams.set("returnTo", pathname);
  return NextResponse.redirect(login);
}

export const config = { matcher: ["/app/:path*", "/admin/:path*"] };
