"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/research/new", label: "New Research" },
];

const RESEARCH = [
  { href: "live", label: "Live Research" },
  { href: "plan", label: "Plan / DAG" },
  { href: "workers", label: "Workers" },
  { href: "sources", label: "Sources" },
  { href: "snapshot", label: "Snapshot" },
  { href: "claims", label: "Claims / Evidence" },
  { href: "quality", label: "Quality / Contradictions" },
  { href: "report", label: "Final Report" },
  { href: "evaluations", label: "Evaluations" },
];

function runIdFromPath(pathname: string): string | null {
  const match = pathname.match(/\/research\/([0-9a-f-]{36})/i) || pathname.match(/\/resume\/([0-9a-f-]{36})/i);
  return match?.[1] ?? null;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const runId = runIdFromPath(pathname);
  const [langsmith, setLangsmith] = useState<{ connected: boolean; project: string; region: string } | null>(null);

  useEffect(() => {
    api.settings().then((data) => {
      const value = data.langsmith as { connected: boolean; project: string; region: string };
      setLangsmith(value);
    }).catch(() => setLangsmith(null));
  }, []);

  return (
    <div className="shell">
      <a className="skip-link" href="#content">Skip to content</a>
      <aside className="sidebar" aria-label="Primary">
        <Link href="/" className="brand"><span className="brand-mark">S</span>DeepScout</Link>
        <nav className="nav">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className="nav-link" aria-current={pathname === item.href ? "page" : undefined}>
              {item.label}
            </Link>
          ))}
          <div className="nav-section">RESEARCH</div>
          {RESEARCH.map((item) => {
            const href = runId
              ? item.href === "live"
                ? `/research/${runId}`
                : item.href === "snapshot"
                  ? `/research/${runId}/sources`
                  : `/research/${runId}/${item.href}`
              : item.href === "live"
                ? "/history"
                : "/research/new";
            const current =
              (item.href === "live" && pathname === `/research/${runId}`) ||
              pathname.endsWith(`/${item.href}`);
            return (
              <Link key={item.href} href={href} className={`nav-link ${current ? "active" : ""}`}>
                {item.label}
                {item.href === "live" && runId ? <span className="nav-dot" /> : null}
              </Link>
            );
          })}
          <Link href="/history" className={`nav-link ${pathname === "/history" ? "active" : ""}`}>History</Link>
          <Link href={runId ? `/resume/${runId}` : "/history"} className={`nav-link ${pathname.startsWith("/resume") ? "active" : ""}`}>Resume</Link>
          <Link href="/settings" className={`nav-link ${pathname === "/settings" ? "active" : ""}`}>Settings</Link>
        </nav>
        <div className="sidebar-foot">
          <div className="status-card">
            <div className="row"><span className={`dot ${langsmith?.connected ? "ok" : "muted"}`} /> LangSmith · {langsmith?.connected ? "Connected" : "Not configured"}</div>
            <div className="muted" style={{ marginTop: 6 }}>{langsmith?.project ?? "deepscout-dev"} ({langsmith?.region ?? "EU"})</div>
          </div>
          <div className="identity-card">
            <strong>Local workspace</strong>
            <div className="muted">Operator</div>
          </div>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <Link href={runId ? `/research/${runId}` : "/"} className="muted">← Back to research</Link>
          <div className="row" aria-label="Utilities">
            <span className="muted">DeepScout</span>
          </div>
        </header>
        <div id="content" className="content">{children}</div>
        <nav className="mobile-nav" aria-label="Mobile">
          <Link href="/">Overview</Link>
          <Link href="/research/new">New</Link>
          <Link href={runId ? `/research/${runId}` : "/history"}>Run</Link>
          <Link href="/history">History</Link>
          <Link href="/settings">Settings</Link>
        </nav>
      </div>
    </div>
  );
}
