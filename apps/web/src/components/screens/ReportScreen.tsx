"use client";

import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";

export function ReportScreen() {
  const { workspace } = useRun();
  const t = useT();
  if (!workspace) return <p className="empty">{t("report.loading")}</p>;
  const report = workspace.report;
  async function copyMarkdown() {
    if (!report) return;
    await navigator.clipboard.writeText(report.body_markdown);
  }
  return (
    <div>
      <RunHeader workspace={workspace} />
      <div className="grid cols-2">
        <article className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2 className="wrap-text">{report?.title ?? t("report.title")}</h2>
            {report ? (
              <div className="row">
                <button className="btn" onClick={() => void copyMarkdown()}>{t("action.copy")}</button>
                <a className="btn" href={api.exportUrl(workspace.run_id, "markdown")}>{t("action.exportMarkdown")}</a>
                <a className="btn" href={api.exportUrl(workspace.run_id, "pdf")}>{t("action.exportPdf")}</a>
                <a className="btn" href={api.exportUrl(workspace.run_id, "json")}>{t("action.exportJson")}</a>
              </div>
            ) : null}
          </div>
          {report ? (
            <pre className="wrap-text">{report.body_markdown}</pre>
          ) : (
            <p className="empty">{t("report.empty")}</p>
          )}
        </article>
        <aside className="drawer">
          <h2>{t("report.info")}</h2>
          <p>{t("report.generatedBy")}</p>
          <p>
            {t("report.model")}: {workspace.llm_model}
          </p>
          <p>{t("table.claims")}: {workspace.counts.claims}</p>
          <p>{t("table.sources")}: {workspace.counts.sources}</p>
          <p>{t("nav.workers")}: {workspace.workers.length}</p>
          <p className="muted">{t("report.citations")}</p>
        </aside>
      </div>
    </div>
  );
}
