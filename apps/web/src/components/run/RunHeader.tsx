"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { elapsed, formatCost, formatTokens } from "@/lib/format";
import type { Workspace } from "@/lib/types";
import { PhaseStepper } from "./PhaseStepper";
import { StatusBadge } from "../StatusBadge";

const TABS = [
  { href: "", label: "Overview" },
  { href: "/plan", label: "Plan / DAG" },
  { href: "/workers", label: "Workers" },
  { href: "/sources", label: "Sources" },
  { href: "/claims", label: "Evidence" },
  { href: "/quality", label: "Quality" },
  { href: "/report", label: "Report" },
  { href: "/evaluations", label: "Evaluations" },
];

export function RunHeader({ workspace }: { workspace: Workspace }) {
  const pathname = usePathname();
  const router = useRouter();
  const base = `/research/${workspace.run_id}`;
  const running = ["running", "pending"].includes(workspace.status);

  async function cancel() {
    await api.cancel(workspace.run_id);
    router.refresh();
  }

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="grow">
          <h1 className="page-title wrap-text">{workspace.goal}</h1>
          <div className="row" style={{ marginTop: 8 }}>
            <StatusBadge status={workspace.status} />
            <span className="muted">Started {elapsed(workspace.started_at ?? workspace.created_at)}</span>
            <span className="mono muted">Research ID: {workspace.run_id}</span>
          </div>
        </div>
        {running ? (
          <button className="btn danger" onClick={() => void cancel()}>Cancel research</button>
        ) : null}
      </div>
      <PhaseStepper completed={workspace.completed_phases} status={workspace.status} />
      <div className="muted" style={{ marginBottom: 8 }}>
        {workspace.llm_provider} · {workspace.llm_model} · tokens {formatTokens(workspace.usage.total_tokens)} · cost {formatCost(workspace.usage.cost_usd, workspace.usage.cost_status)}
      </div>
      <nav className="tabs" aria-label="Research sections">
        {TABS.map((tab) => {
          const href = `${base}${tab.href}`;
          const active = tab.href === "" ? pathname === base : pathname.startsWith(href);
          return (
            <Link key={tab.href || "overview"} href={href} className={`tab ${active ? "active" : ""}`}>
              {tab.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
