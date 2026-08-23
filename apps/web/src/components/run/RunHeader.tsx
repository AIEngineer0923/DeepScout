"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Workspace } from "@/lib/types";
import { elapsed, formatDuration, formatResearchMode } from "@/lib/format";
import { StatusBadge } from "../StatusBadge";
import { PhaseStepper } from "./PhaseStepper";
import { useT, useI18n } from "@/i18n/context";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import { DemoNotice } from "@/components/demo/DemoNotice";
import { TechnicalDetails } from "@/components/demo/TechnicalDetails";
import { presentOutputLanguage } from "@/presentation/fields";
import { ResearchGoalHeading } from "@/components/research/ResearchGoalHeading";

export function RunHeader({ workspace }: { workspace: Workspace }) {
  const router = useRouter();
  const t = useT();
  const { locale } = useI18n();
  const demoReadOnly = useDemoReadOnly();
  const running = ["running", "pending"].includes(workspace.status);
  const completed = ["completed", "failed", "cancelled"].includes(workspace.status);

  async function cancel() {
    const { api } = await import("@/lib/api");
    await api.cancel(workspace.run_id);
    router.refresh();
  }

  return (
    <header
      className={`research-header ${demoReadOnly ? "demo-research-header" : ""}`}
      data-testid="research-header"
    >
      <div className="research-header-main">
        <div className="research-header-copy">
          <ResearchGoalHeading workspace={workspace} locale={locale} />
          <div className="research-meta">
            <StatusBadge status={workspace.status} />
            <span className="meta-dot" aria-hidden="true">
              ·
            </span>
            <span className="muted">
              {completed
                ? formatDuration(workspace.started_at ?? workspace.created_at, workspace.completed_at)
                : elapsed(workspace.started_at ?? workspace.created_at)}
            </span>
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
                <span>{presentOutputLanguage(workspace.output_language, locale)}</span>
              </>
            ) : null}
          </div>
        </div>
        {!demoReadOnly && running ? (
          <button className="btn danger" onClick={() => void cancel()}>
            {t("action.cancelResearch")}
          </button>
        ) : null}
      </div>
      {demoReadOnly ? (
        <DemoNotice
          action={
            <Link href="/login?next=/research/new" className="btn primary">
              {t("demo.cta")}
            </Link>
          }
        />
      ) : (
        <div className="info-banner">{t("live.banner")}</div>
      )}
      {!completed ? <PhaseStepper completed={workspace.completed_phases} status={workspace.status} /> : null}
      <TechnicalDetails workspace={workspace} />
    </header>
  );
}
