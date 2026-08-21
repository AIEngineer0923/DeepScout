"use client";

import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useRun } from "@/components/run/RunProvider";
import { StatusBadge } from "@/components/StatusBadge";

export function ResumeScreen() {
  const { workspace, reload } = useRun();
  const router = useRouter();
  if (!workspace) return <p className="empty">Loading resume state…</p>;
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
      <h1 className="page-title">Resume research</h1>
      <p className="page-sub">PostgreSQL domain state is authoritative. LangGraph checkpoints store worker execution snapshots only.</p>
      <div className="row" style={{ margin: "16px 0" }}>
        <button className="btn primary" disabled={!resume.resumable} onClick={() => void doResume()}>Resume research</button>
        <button className="btn" onClick={() => void doRestart()}>Restart from beginning</button>
        {["running", "pending"].includes(workspace.status) ? (
          <button className="btn danger" onClick={() => void api.cancel(workspace.run_id).then(reload)}>Cancel research</button>
        ) : null}
      </div>
      <p className="wrap-text"><strong>{workspace.goal}</strong></p>
      <StatusBadge status={workspace.status} />
      <div className="grid cols-3" style={{ marginTop: 16 }}>
        <article className="card">
          <h2>Last persisted state</h2>
          <p>Current phase: {resume.current_phase}</p>
          <p>Latest job: {resume.latest_job_type ?? "—"} ({resume.latest_job_status ?? "none"})</p>
          <p>Checkpoint role: {resume.checkpoint_role.replaceAll("_", " ")}</p>
        </article>
        <article className="card">
          <h2>What’s been completed</h2>
          <p>{resume.completed_task_count} completed tasks</p>
          <p>{resume.preserved_sources} sources preserved</p>
          <p>{resume.preserved_evidence} evidence items preserved</p>
        </article>
        <article className="card">
          <h2>Remaining work</h2>
          <p>{resume.remaining_task_count} recoverable / remaining tasks</p>
          <p className="muted">Resume continues the existing run. Restart creates a new run with the same goal.</p>
        </article>
      </div>
    </div>
  );
}
