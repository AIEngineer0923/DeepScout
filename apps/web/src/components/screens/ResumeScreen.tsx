"use client";

import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useRun } from "@/components/run/RunProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { useT } from "@/i18n/context";

export function ResumeScreen() {
  const { workspace, reload } = useRun();
  const t = useT();
  const router = useRouter();
  if (!workspace) return <p className="empty">{t("resume.loading")}</p>;
  const resume = workspace.resume;
  async function doResume() {
    await api.resume(workspace!.run_id);
    reload();
    router.push(`/research/${workspace!.run_id}`);
  }
  async function doRestart() {
    const created = await api.restart(workspace!.run_id);
    router.push(`/research/${created.run_id}`);
  }
  return (
    <div>
      <h1 className="page-title">{t("resume.title")}</h1>
      <p className="page-sub">{t("resume.subtitle")}</p>
      <div className="row" style={{ margin: "16px 0" }}>
        <button className="btn primary" disabled={!resume.resumable} onClick={() => void doResume()}>{t("action.resume")}</button>
        <button className="btn" onClick={() => void doRestart()}>{t("action.restart")}</button>
        {["running", "pending"].includes(workspace.status) ? (
          <button className="btn danger" onClick={() => void api.cancel(workspace.run_id).then(reload)}>{t("action.cancelResearch")}</button>
        ) : null}
      </div>
      <p className="wrap-text"><strong>{workspace.goal}</strong></p>
      <StatusBadge status={workspace.status} />
      <div className="grid cols-3" style={{ marginTop: 16 }}>
        <article className="card">
          <h2>{t("resume.lastState")}</h2>
          <p>Current phase: {resume.current_phase}</p>
          <p>Latest job: {resume.latest_job_type ?? "—"} ({resume.latest_job_status ?? "none"})</p>
          <p>Checkpoint role: {resume.checkpoint_role.replaceAll("_", " ")}</p>
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
