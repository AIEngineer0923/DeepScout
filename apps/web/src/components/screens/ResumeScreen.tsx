"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useRun } from "@/components/run/RunProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { useI18n, useT } from "@/i18n/context";
import { ResearchGoalHeading } from "@/components/research/ResearchGoalHeading";
import { presentCheckpointRole, presentJob, presentRuntimePhase } from "@/presentation/product";

export function ResumeScreen() {
  const { workspace, reload } = useRun();
  const t = useT();
  const { locale } = useI18n();
  const router = useRouter();
  const [pendingReviewId, setPendingReviewId] = useState<string | null>(null);
  const [pendingReviewType, setPendingReviewType] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!workspace || workspace.status !== "paused") {
      setPendingReviewId(null);
      setPendingReviewType(null);
      return;
    }
    api
      .listRunReviews(workspace.run_id)
      .then((rows) => {
        const pending = rows.find((row) => row.status === "pending");
        setPendingReviewId(pending ? String(pending.id) : null);
        setPendingReviewType(pending ? String(pending.proposed_action_type) : null);
      })
      .catch(() => {
        setPendingReviewId(null);
        setPendingReviewType(null);
      });
  }, [workspace]);

  if (!workspace) return <p className="empty">{t("resume.loading")}</p>;
  const resume = workspace.resume;
  const awaiting = workspace.status === "paused";

  async function doResume() {
    await api.resume(workspace!.run_id);
    reload();
    router.push(`/research/${workspace!.run_id}`);
  }
  async function doRestart() {
    const created = await api.restart(workspace!.run_id);
    router.push(`/research/${created.run_id}`);
  }
  async function approvePending() {
    if (!pendingReviewId) return;
    setError(null);
    try {
      await api.approveReview(workspace!.run_id, pendingReviewId);
      reload();
      router.push(`/research/${workspace!.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("reviews.approvalFailed"));
    }
  }

  return (
    <div>
      <h1 className="page-title">{t("resume.title")}</h1>
      <p className="page-sub">{t("resume.subtitle")}</p>
      {awaiting ? (
        <div className="card" style={{ marginBottom: 16 }} role="status">
          <h2>{t("reviews.waiting")}</h2>
          <p>{t("reviews.subtitle")}</p>
          <div className="row" style={{ gap: 8 }}>
            {pendingReviewType === "budget_extension" ? (
              <button className="btn primary" disabled={!pendingReviewId} onClick={() => void approvePending()}>
                {t("reviews.approve")}
              </button>
            ) : null}
            <Link className="btn" href="/reviews">
              {pendingReviewType === "human_input" ? t("reviews.yourResponse") : t("nav.reviews")}
            </Link>
          </div>
          {error ? <p className="error">{error}</p> : null}
        </div>
      ) : null}
      <div className="row" style={{ margin: "16px 0" }}>
        <button className="btn primary" disabled={!resume.resumable || awaiting} onClick={() => void doResume()}>
          {t("action.resume")}
        </button>
        <button className="btn" onClick={() => void doRestart()}>
          {t("action.restart")}
        </button>
        <button
          className="btn"
          onClick={() =>
            void api.fork(workspace.run_id).then((created) => router.push(`/research/${created.run_id}`))
          }
        >
          {t("action.fork")}
        </button>
        {["running", "pending", "paused"].includes(workspace.status) ? (
          <button className="btn danger" onClick={() => void api.cancel(workspace.run_id).then(reload)}>
            {t("action.cancelResearch")}
          </button>
        ) : null}
      </div>
      <ResearchGoalHeading workspace={workspace} locale={locale} level={2} className="resume-research-title" />
      <StatusBadge status={workspace.status} />
      <div className="grid cols-3" style={{ marginTop: 16 }}>
        <article className="card">
          <h2>{t("resume.lastState")}</h2>
          <p>{t("resume.currentPhase")}: {presentRuntimePhase(resume.current_phase, locale)}</p>
          <p>
            {t("resume.latestJob")}: {presentJob(resume.latest_job_type, locale)} ({presentJob(resume.latest_job_status, locale)})
          </p>
          <p>{t("resume.checkpoint")}: {presentCheckpointRole(resume.checkpoint_role, locale)}</p>
        </article>
        <article className="card">
          <h2>{t("resume.completed")}</h2>
          <p>{t("resume.completedTasks", { count: resume.completed_task_count })}</p>
          <p>{t("resume.sources", { count: resume.preserved_sources })}</p>
          <p>{t("resume.evidence", { count: resume.preserved_evidence })}</p>
        </article>
        <article className="card">
          <h2>{t("resume.remaining")}</h2>
          <p>{t("resume.remainingTasks", { count: resume.remaining_task_count })}</p>
          <p className="muted">{t("resume.note")}</p>
        </article>
      </div>
    </div>
  );
}
