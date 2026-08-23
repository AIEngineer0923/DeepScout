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
import { presentContradiction } from "@/presentation/contradictions";

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
        {workspace.contradictions.map((item) => {
          const claimA = claimById[item.claim_a_id];
          const claimB = claimById[item.claim_b_id];
          return (
            <article key={item.id} className="card contradiction-card">
              <div className="contradiction-head">
                <StatusBadge status={item.evidence_status} />
              </div>
              <p className="contradiction-summary">
                {presentContradiction(item.description, locale)}
              </p>
              <dl className="contradiction-pair">
                <div className="contradiction-side">
                  <dt>{t("quality.claimA")}</dt>
                  <dd className="wrap-text">
                    {claimA
                      ? displayClaimStatement(workspace, item.claim_a_id, claimA.statement)
                      : "—"}
                  </dd>
                </div>
                <div className="contradiction-side">
                  <dt>{t("quality.claimB")}</dt>
                  <dd className="wrap-text">
                    {claimB
                      ? displayClaimStatement(workspace, item.claim_b_id, claimB.statement)
                      : "—"}
                  </dd>
                </div>
              </dl>
              <Link href={`/research/${workspace.run_id}/claims`}>{t("quality.inspect")}</Link>
            </article>
          );
        })}
      </section>
    </div>
  );
}
