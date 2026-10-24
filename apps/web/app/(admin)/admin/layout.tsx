import { redirect } from "next/navigation";
import Shell, { NavItem } from "@/components/layout/Shell";
import { currentSession } from "@/lib/session";

const ITEMS: NavItem[] = [
  { href: "/admin", label: "Overview", icon: "home" },
  { href: "/admin/agents", label: "Agents & models", icon: "cpu" },
  { href: "/admin/models", label: "Model registry", icon: "sliders" },
  { href: "/admin/skills", label: "Skills", icon: "book" },
  { href: "/admin/sources", label: "Source health", icon: "server" },
  { href: "/admin/usage", label: "Usage & cost", icon: "coin" },
  { href: "/admin/releases", label: "Releases", icon: "list" },
  { href: "/admin/audit", label: "Audit history", icon: "shield" },
  { href: "/admin/help", label: "How it works", icon: "help" },
];

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await currentSession();
  if (!session) redirect("/admin/login");
  if (session.kind !== "admin" || session.user.role !== "platform_admin") redirect("/access-denied?reason=wrong-role");
  return <Shell title="Administration" items={ITEMS} session={session}>{children}</Shell>;
}
