"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { elapsed, formatCost, formatTokens } from "@/lib/format";
import type { Workspace } from "@/lib/types";
import { PhaseStepper } from "./PhaseStepper";
import { StatusBadge } from "../StatusBadge";
import { useT } from "@/i18n/context";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";

const TABS = [
  { href: "", key: "tab.overview" },
  { href: "/plan", key: "tab.plan" },
  { href: "/workers", key: "tab.workers" },
  { href: "/sources", key: "tab.sources" },
  { href: "/snapshots", key: "tab.snapshot" },
  { href: "/claims", key: "tab.evidence" },
  { href: "/quality", key: "tab.quality" },
  { href: "/report", key: "tab.report" },
  { href: "/evaluations", key: "tab.evaluations" },
];

export function RunHeader({ workspace }: { workspace: Workspace }) {
  const pathname = usePathname();
  const router = useRouter();
  const t = useT();
  const demoReadOnly = useDemoReadOnly();
  const base = `/research/${workspace.run_id}`;
  const running = ["running", "pending"].includes(workspace.status);

  async function cancel() {
    await api.cancel(workspace.run_id);
    router.refresh();
  }

  return (
    <div style={{ marginBottom: 8 }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div className="grow">
          <h1 className="page-title wrap-text">{workspace.goal}</h1>
          <div className="run-meta">
            <StatusBadge status={workspace.status} />
            <span className="muted">{elapsed(workspace.started_at ?? workspace.created_at)}</span>
            <span className="mono muted">{workspace.run_id}</span>
            {workspace.research_mode ? <span className="chip selected">{workspace.research_mode}</span> : null}
            {workspace.output_language ? <span className="chip">{workspace.output_language}</span> : null}
          </div>
        </div>
        {running && !demoReadOnly ? (
          <button className="btn danger" onClick={() => void cancel()}>
            {t("action.cancelResearch")}
          </button>
        ) : demoReadOnly ? (
          <Link href="/login" className="btn primary">
            {t("demo.cta")}
          </Link>
        ) : null}
      </div>
      <PhaseStepper completed={workspace.completed_phases} status={workspace.status} />
      <div className="info-banner">{demoReadOnly ? t("demo.replayBanner") : t("live.banner")}</div>
      <div className="muted" style={{ marginBottom: 8, fontSize: 13 }}>
        {workspace.llm_provider} · {workspace.llm_model} · {t("provider.tokens")}{" "}
        {formatTokens(workspace.usage.total_tokens, t("cost.unknown"))} · {t("provider.appCost")}{" "}
        {formatCost(workspace.usage.cost_usd, workspace.usage.cost_status, t("cost.unknown"))}
      </div>
      <nav className="tabs" aria-label={t("nav.research")}>
        {TABS.map((tab) => {
          const href = `${base}${tab.href}`;
          const active = tab.href === "" ? pathname === base : pathname.startsWith(href);
          return (
            <Link key={tab.href || "overview"} href={href} className={`tab ${active ? "active" : ""}`} aria-current={active ? "page" : undefined}>
              {t(tab.key)}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
