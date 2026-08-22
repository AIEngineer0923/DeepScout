"use client";

import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { useI18n, useT } from "@/i18n/context";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import { displayClaimStatement } from "@/presentation/demo";
import {
  presentEvaluator,
  presentEvaluationOutcome,
} from "@/presentation/evaluators";

export function QualityScreen() {
  const { workspace } = useRun();
  const t = useT();
  const { locale } = useI18n();
  const demoReadOnly = useDemoReadOnly();
  if (!workspace) return <p className="empty">{t("quality.loading")}</p>;
  const claimById = Object.fromEntries(workspace.claims.map((claim) => [claim.id, claim]));
  const deterministic = workspace.evaluations.filter(
    (item) => item.method === "deterministic_code" && item.status !== "not_applicable",
  );
  return (
    <div>
      <RunHeader workspace={workspace} />
      <section className="card">
        <h2>{t("quality.checks")}</h2>
        <p className="muted">{demoReadOnly ? t("demo.quality.intro") : t("quality.note")}</p>
        <div className="grid cols-metrics">
          {deterministic.slice(0, 6).map((item) => {
            const presented = presentEvaluator(item.evaluator_id, locale, item.description);
            return (
              <article key={item.evaluator_id} className="metric">
                <div className="k">{presented.title}</div>
                <div className="v" style={{ fontSize: 16 }}>
                  {presentEvaluationOutcome(item.evaluator_id, item, locale)}
                </div>
              </article>
            );
          })}
        </div>
      </section>
      <section className="card" style={{ marginTop: 16 }}>
        <h2>{t("quality.contradictions", { count: workspace.contradictions.length })}</h2>
        {workspace.contradictions.length === 0 ? <p className="empty">{t("quality.none")}</p> : null}
        {workspace.contradictions.map((item) => (
          <article key={item.id} className="card" style={{ marginBottom: 12 }}>
            <StatusBadge status={item.evidence_status} />
            <p className="wrap-text">{item.description}</p>
            <p className="wrap-text">
              {t("table.claims")}:{" "}
              {claimById[item.claim_a_id]
                ? displayClaimStatement(workspace, item.claim_a_id, claimById[item.claim_a_id].statement)
                : "—"}{" "}
              ·{" "}
              {claimById[item.claim_b_id]
                ? displayClaimStatement(workspace, item.claim_b_id, claimById[item.claim_b_id].statement)
                : "—"}
            </p>
            <Link href={`/research/${workspace.run_id}/claims`}>{t("quality.inspect")}</Link>
          </article>
        ))}
      </section>
    </div>
  );
}
