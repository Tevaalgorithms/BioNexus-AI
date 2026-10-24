"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

export default function NavLink({ href, children }: { href: string; children: ReactNode }) {
  const path = usePathname();
  const root = href === "/app" || href === "/admin";
  const active = root ? path === href : path.startsWith(href);
  return <Link className="item" href={href} aria-current={active ? "page" : undefined}>{children}</Link>;
}
