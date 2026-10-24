import { NextResponse } from "next/server";
import { currentSession } from "@/lib/session";

/** Gives the page its CSRF token and display identity; never any credential. */
export async function GET() {
  const session = await currentSession();
  if (!session) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  return NextResponse.json({ csrf: session.csrf, user: session.user, kind: session.kind });
}
