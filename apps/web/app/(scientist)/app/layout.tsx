import { redirect } from "next/navigation";
import Shell, { NavItem } from "@/components/layout/Shell";
import { currentSession } from "@/lib/session";

const ITEMS: NavItem[] = [
  { href: "/app", label: "Dashboard", icon: "home" },
  { href: "/app/projects", label: "Projects", icon: "list" },
  { href: "/app/new", label: "New analysis", icon: "plus" },
  { href: "/app/review", label: "Review queue", icon: "review" },
  { href: "/app/help", label: "How it works", icon: "help" },
  { href: "/app/account", label: "Account", icon: "user" },
];

export default async function ScientistLayout({ children }: { children: React.ReactNode }) {
  const session = await currentSession();
  if (!session) redirect("/login");
  if (session.kind !== "scientist") redirect("/access-denied?reason=wrong-role");
  return <Shell title="Research" items={ITEMS} session={session}>{children}</Shell>;
}
