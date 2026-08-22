"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import { displayReport } from "@/presentation/demo";
import { RichContent } from "@/components/RichContent";
import { truncateMarkdownBody } from "@/lib/markdown";

const SUGGESTIONS = [
  "Dig deeper into the strongest claim.",
  "Find newer evidence.",
  "Why do these sources disagree?",
  "Verify the most cited statement.",
];

export function ReportScreen() {
  const { workspace } = useRun();
  const t = useT();
  const demoReadOnly = useDemoReadOnly();
  const router = useRouter();
  const [followup, setFollowup] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);
  if (!workspace) return <p className="empty">{t("report.loading")}</p>;
  const current = workspace;
  const reportView = displayReport(current);
  const parentId = workspace.runtime?.parent_run_id;
  const bodyPreviewLimit = 6000;
  const { body: previewBody, truncated: hasMoreBody } = reportView.body
    ? truncateMarkdownBody(reportView.body, bodyPreviewLimit)
    : { body: "", truncated: false };
  const showReadMore = Boolean(hasMoreBody && !expanded);
  const renderedBody = showReadMore ? previewBody : reportView.body;

  async function copyMarkdown() {
    if (!reportView.body) return;
    try {
      await navigator.clipboard.writeText(reportView.body);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError(t("report.copyFailed"));
    }
  }

  async function startFollowUp() {
    const goal = followup.trim();
    if (!goal) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.followUp(current.run_id, { goal, inherit_source_preferences: true });
      router.push(`/research/${created.run_id}`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : t("followup.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <RunHeader workspace={workspace} />
      <div className="grid cols-2">
        <article className="card report-document">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2 className="wrap-text">{reportView.title || t("report.title")}</h2>
            {reportView.body ? (
              <div className="row">
                <button
                  className="btn"
                  type="button"
                  aria-live="polite"
                  onClick={() => void copyMarkdown()}
                >
                  {copied ? t("report.copied") : t("action.copyReport")}
                </button>
                <a className="btn" href={api.exportUrl(workspace.run_id, "markdown")}>
                  {t("action.exportMarkdown")}
                </a>
                <a className="btn" href={api.exportUrl(workspace.run_id, "pdf")}>
                  {t("action.exportPdf")}
                </a>
                {!demoReadOnly ? (
                  <a className="btn" href={api.exportUrl(workspace.run_id, "json")}>
                    {t("action.exportJson")}
                  </a>
                ) : null}
              </div>
            ) : null}
          </div>
          {renderedBody ? (
            <>
              <RichContent
                markdown={renderedBody}
                className="rich-content report-body-selectable"
                runId={workspace.run_id}
                sources={workspace.sources}
              />
              {showReadMore ? (
                <button
                  className="btn"
                  type="button"
                  onClick={() => setExpanded(true)}
                  aria-expanded={expanded}
                >
                  {t("report.readMore")}
                </button>
              ) : hasMoreBody && expanded ? (
                <button
                  className="btn"
                  type="button"
                  onClick={() => setExpanded(false)}
                  aria-expanded={expanded}
                >
                  {t("report.readLess")}
                </button>
              ) : null}
            </>
          ) : (
            <p className="empty">{t("report.empty")}</p>
          )}
        </article>
        <aside className="drawer">
          <h2>{t("report.info")}</h2>
          <p>{t("report.generatedBy")}</p>
          {!demoReadOnly ? (
            <p>
              {t("report.model")}: {workspace.llm_model}
            </p>
          ) : null}
          <p>{t("table.claims")}: {workspace.counts.claims}</p>
          <p>{t("table.sources")}: {workspace.counts.sources}</p>
          <p>{t("nav.workers")}: {workspace.workers.length}</p>
          {parentId ? (
            <p>
              <a href={`/research/${parentId}/report`}>{t("followup.parent")}</a>
            </p>
          ) : null}
          {workspace.runtime?.lineage_kind && workspace.runtime.lineage_kind !== "none" ? (
            <p className="muted">{t("lineage." + workspace.runtime.lineage_kind)}</p>
          ) : null}
          <p className="muted">{t("report.citations")}</p>
          {!demoReadOnly ? (
            <>
              <h2 style={{ marginTop: 24 }}>{t("followup.title")}</h2>
              <p className="muted">{t("followup.help")}</p>
              <textarea
                className="input"
                data-testid="followup-input"
                rows={4}
                value={followup}
                onChange={(e) => setFollowup(e.target.value)}
                placeholder={t("followup.placeholder")}
              />
              <div className="row" style={{ flexWrap: "wrap", gap: 8, margin: "8px 0" }}>
                {SUGGESTIONS.map((item) => (
                  <button key={item} type="button" className="btn" onClick={() => setFollowup(item)}>
                    {item}
                  </button>
                ))}
              </div>
              {error ? <p className="empty">{error}</p> : null}
              <button
                className="btn primary"
                data-testid="followup-start"
                disabled={busy || !followup.trim()}
                onClick={() => void startFollowUp()}
              >
                {busy ? t("followup.starting") : t("followup.start")}
              </button>
            </>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
