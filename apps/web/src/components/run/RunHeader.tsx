"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { Workspace } from "@/lib/types";
import { elapsed, formatResearchMode } from "@/lib/format";
import { StatusBadge } from "../StatusBadge";
import { PhaseStepper } from "./PhaseStepper";
import { useT, useI18n } from "@/i18n/context";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import { DemoNotice } from "@/components/demo/DemoNotice";
import { TechnicalDetails } from "@/components/demo/TechnicalDetails";
import { displayGoal } from "@/presentation/demo";

export function RunHeader({ workspace }: { workspace: Workspace }) {
  const pathname = usePathname();
  const router = useRouter();
  const t = useT();
  const { locale } = useI18n();
  const demoReadOnly = useDemoReadOnly();
  const base = `/research/${workspace.run_id}`;
  const running = ["running", "pending"].includes(workspace.status);
  const completed = ["completed", "failed", "cancelled"].includes(workspace.status);
  const title = displayGoal(workspace, locale);

  async function cancel() {
    const { api } = await import("@/lib/api");
    await api.cancel(workspace.run_id);
    router.refresh();
  }

  if (demoReadOnly) {
    return (
      <header className="research-header demo-research-header" data-testid="research-header">
        <div className="research-header-main">
          <div className="research-header-copy">
            <h1 className="research-title">{title}</h1>
            <div className="research-meta">
              <StatusBadge status={workspace.status} />
              <span className="meta-dot" aria-hidden="true">
                ·
              </span>
              <span className="muted">{elapsed(workspace.started_at ?? workspace.created_at)}</span>
              {workspace.research_mode ? (
                <>
                  <span className="meta-dot" aria-hidden="true">
                    ·
                  </span>
                  <span>{formatResearchMode(workspace.research_mode, t)}</span>
                </>
              ) : null}
              {workspace.output_language ? (
                <>
                  <span className="meta-dot" aria-hidden="true">
                    ·
                  </span>
                  <span>{workspace.output_language}</span>
                </>
              ) : null}
            </div>
          </div>
          <div className="research-header-cta">
            <Link href="/login" className="btn primary">
              {t("demo.cta")}
            </Link>
          </div>
        </div>
        <DemoNotice />
        {!completed ? <PhaseStepper completed={workspace.completed_phases} status={workspace.status} /> : null}
        <TechnicalDetails workspace={workspace} />
      </header>
    );
  }

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

  return (
    <header className="research-header" data-testid="research-header">
      <div className="research-header-main">
        <div className="research-header-copy">
          <h1 className="research-title">{title}</h1>
          <div className="research-meta">
            <StatusBadge status={workspace.status} />
            <span className="meta-dot" aria-hidden="true">
              ·
            </span>
            <span className="muted">{elapsed(workspace.started_at ?? workspace.created_at)}</span>
            {workspace.research_mode ? (
              <>
                <span className="meta-dot" aria-hidden="true">
                  ·
                </span>
                <span>{formatResearchMode(workspace.research_mode, t)}</span>
              </>
            ) : null}
          </div>
        </div>
        {running ? (
          <button className="btn danger" onClick={() => void cancel()}>
            {t("action.cancelResearch")}
          </button>
        ) : null}
      </div>
      <PhaseStepper completed={workspace.completed_phases} status={workspace.status} />
      <div className="info-banner">{t("live.banner")}</div>
      <TechnicalDetails workspace={workspace} />
      <nav className="tabs" aria-label={t("nav.research")}>
        {TABS.map((tab) => {
          const href = `${base}${tab.href}`;
          const active = tab.href === "" ? pathname === base : pathname.startsWith(href);
          return (
            <Link
              key={tab.href || "overview"}
              href={href}
              className={`tab ${active ? "active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              {t(tab.key)}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
