import { ReactNode } from "react";
import Link from "next/link";
import { Session } from "@/lib/session";
import { Icon, IconName } from "./icons";
import { Logo } from "./illustrations";
import NavLink from "./NavLink";
import ThemeToggle from "./ThemeToggle";

export interface NavItem { href: string; label: string; icon: IconName }

export default function Shell({ title, items, session, children }: { title: string; items: NavItem[]; session: Session; children: ReactNode }) {
  const initials = session.user.user_id.slice(0, 2).toUpperCase();
  return (
    <div className="shell">
      <nav className="nav" aria-label={`${title} navigation`}>
        <Link href="/" className="brand"><Logo /> BioNexus AI</Link>
        <div className="nav-label">{title}</div>
        {items.map((item) => (
          <NavLink key={item.href} href={item.href}><Icon name={item.icon} /> {item.label}</NavLink>
        ))}
        <div className="spacer" />
        <div className="user">
          <div className="avatar" aria-hidden="true">{initials}</div>
          <div><strong>{session.user.user_id}</strong><small>{session.user.role.replace("_", " ")} · {session.user.tenant_id}</small></div>
        </div>
        <form method="post" action="/api/auth/logout">
          <input type="hidden" name="csrf" value={session.csrf} />
          <button className="side" type="submit">Sign out</button>
        </form>
        <ThemeToggle />
      </nav>
      <main id="content" tabIndex={-1}>{children}</main>
    </div>
  );
}
