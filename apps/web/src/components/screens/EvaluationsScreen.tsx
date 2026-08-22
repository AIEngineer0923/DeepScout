"use client";

import { useMemo, useState } from "react";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { api } from "@/lib/api";
import { useI18n, useT } from "@/i18n/context";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import {
  presentEvaluator,
  presentEvaluationOutcome,
  presentEvaluatorApplicability,
  presentEvaluatorCategory,
  presentEvaluatorMethod,
  shouldShowEvaluationRow,
} from "@/presentation/evaluators";

export function EvaluationsScreen() {
  const { workspace } = useRun();
  const t = useT();
  const { locale } = useI18n();
  const demoReadOnly = useDemoReadOnly();
  const [query, setQuery] = useState("");
  const rows = useMemo(() => {
    if (!workspace) return [];
    const q = query.toLowerCase();
    return workspace.evaluations.filter((item) => {
      if (!shouldShowEvaluationRow(item.applicability)) return false;
      if (!q) return true;
      const presented = presentEvaluator(item.evaluator_id, locale, item.description);
      return `${presented.title} ${presented.description} ${item.category}`.toLowerCase().includes(q);
    });
  }, [workspace, query, locale]);

  if (!workspace) return <p className="empty">{t("evals.loading")}</p>;

  const groups = Array.from(new Set(rows.map((item) => item.category)));

  return (
    <div className="evaluations-page">
      <RunHeader workspace={workspace} />
      <p className="screen-intro">
        {workspace.evaluations_deferred
          ? t("evals.deferred")
          : demoReadOnly
            ? t("demo.eval.intro")
            : t("evals.note")}
      </p>
      {!demoReadOnly ? (
        <div className="row eval-actions">
          <a className="btn" href={api.exportUrl(workspace.run_id, "evals-json")}>
            {t("action.exportEvals")} JSON
          </a>
          <a className="btn" href={api.exportUrl(workspace.run_id, "evals-csv")}>
            {t("action.exportEvals")} CSV
          </a>
        </div>
      ) : null}
      <input
        className="input"
        placeholder={t("evals.filter")}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {groups.map((group) => {
        const items = rows.filter((item) => item.category === group);
        if (!items.length) return null;
        return (
          <section key={group} className="card eval-group" style={{ marginTop: 16 }}>
            <h2>{presentEvaluatorCategory(group, locale)}</h2>
            <div className="eval-grid">
              {items.map((item) => {
                const presented = presentEvaluator(item.evaluator_id, locale, item.description);
                return (
                  <article key={`${item.evaluator_id}-${item.version}`} className="eval-card">
                    <h3>{presented.title}</h3>
                    <p className="muted eval-description">{presented.description}</p>
                    <dl className="kv-list compact">
                      <div className="kv-row">
                        <dt>{t("table.result")}</dt>
                        <dd>{presentEvaluationOutcome(item.evaluator_id, item, locale)}</dd>
                      </div>
                      {item.reason ? (
                        <div className="kv-row">
                          <dt>{t("table.reason")}</dt>
                          <dd className="wrap-text">{item.reason}</dd>
                        </div>
                      ) : null}
                      <div className="kv-row">
                        <dt>{t("table.method")}</dt>
                        <dd>{presentEvaluatorMethod(item.method, locale)}</dd>
                      </div>
                      <div className="kv-row">
                        <dt>{t("table.applicability")}</dt>
                        <dd>{presentEvaluatorApplicability(item.applicability, locale)}</dd>
                      </div>
                    </dl>
                  </article>
                );
              })}
            </div>
          </section>
        );
      })}
      {rows.length === 0 ? <p className="empty">{t("evals.empty")}</p> : null}
    </div>
  );
}
