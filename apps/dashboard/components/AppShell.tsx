"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/targets", label: "Targets" },
  { href: "/scans", label: "Scans" },
  { href: "/findings", label: "Findings" },
  { href: "/approvals", label: "Approvals" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  if (pathname === "/login") {
    return <main className="auth-page">{children}</main>;
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">Aegis Mesh</div>
        <nav>
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={pathname === item.href ? "nav-link active" : "nav-link"}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        {user && (
          <div className="sidebar-footer">
            <div className="user-email">{user.email}</div>
            <button className="btn-link" onClick={logout}>
              Sign out
            </button>
          </div>
        )}
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
