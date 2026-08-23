"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useI18n } from "@/i18n/context";
import { ClampedText } from "@/components/ClampedText";
import { formatCost, formatTokens } from "@/lib/format";
import { presentCostStatus } from "@/presentation/product";

export function CompareScreen() {
  const { t, locale } = useI18n();
  const params = useSearchParams();
  const [left, setLeft] = useState(params.get("left") ?? "");
  const [right, setRight] = useState(params.get("right") ?? "");
  const [diff, setDiff] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function run() {
    setError(null);
    try {
      setDiff(await api.diffRuns(left, right));
    } catch (exc) {
      setDiff(null);
      setError(exc instanceof Error ? exc.message : t("compare.failed"));
    }
  }
  useEffect(() => {
    if (params.get("left") && params.get("right")) void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const sources = (diff?.sources as { added?: string[]; removed?: string[]; unchanged?: string[] }) ?? {};
  const claims = (diff?.claims as { added?: string[]; removed?: string[]; unchanged?: number }) ?? {};
  const plan = diff?.plan as {
    left?: { task_count?: number; critical_path_depth?: number; parallel_width?: number; edges?: number };
    right?: { task_count?: number; critical_path_depth?: number; parallel_width?: number; edges?: number };
  } | undefined;
  const usage = diff?.usage as { left?: { total_tokens?: number | null; cost_usd?: number | null; cost_status?: string }; right?: { total_tokens?: number | null; cost_usd?: number | null; cost_status?: string } } | undefined;
  return (
    <div>
      <h1 className="page-title">{t("compare.title")}</h1>
      <p className="page-sub">{t("compare.subtitle")}</p>
      <div className="toolbar">
        <input className="input grow" value={left} onChange={(e) => setLeft(e.target.value)} aria-label={t("compare.left")} />
        <input className="input grow" value={right} onChange={(e) => setRight(e.target.value)} aria-label={t("compare.right")} />
        <button className="btn primary" data-testid="compare-run" type="button" onClick={() => void run()}>{t("compare.run")}</button>
      </div>
      {error ? <p className="empty">{error}</p> : null}
      {diff ? (
        <div className="grid cols-2">
          <article className="card">
            <h2>{t("compare.summary")}</h2>
            <p>
              {t("compare.left")}: <ClampedText lines={3}>{String((diff.left as { goal?: string })?.goal)}</ClampedText>
            </p>
            <p>
              {t("compare.right")}: <ClampedText lines={3}>{String((diff.right as { goal?: string })?.goal)}</ClampedText>
            </p>
            <h3>{t("nav.plan")}</h3>
            <dl className="kv-list">
              {(["task_count", "critical_path_depth", "parallel_width", "edges"] as const).map((key) => (
                <div className="kv-row" key={key}>
                  <dt>{t(`compare.plan.${key}`)}</dt>
                  <dd>{plan?.left?.[key] ?? "—"} → {plan?.right?.[key] ?? "—"}</dd>
                </div>
              ))}
            </dl>
          </article>
          <article className="card">
            <h2>{t("nav.sources")}</h2>
            <p>{t("compare.added")}: {(sources.added ?? []).length}</p>
            <p>{t("compare.removed")}: {(sources.removed ?? []).length}</p>
            <p>{t("compare.unchanged")}: {(sources.unchanged ?? []).length}</p>
          </article>
          <article className="card">
            <h2>{t("nav.claims")}</h2>
            <ul>{(claims.added ?? []).slice(0, 8).map((item) => <li key={item} className="wrap-text">{item}</li>)}</ul>
            <p>{t("compare.unchanged")}: {claims.unchanged ?? 0}</p>
          </article>
          <article className="card">
            <h2>{t("compare.usage")}</h2>
            {(["left", "right"] as const).map((side) => (
              <div key={side} style={{ marginTop: 12 }}>
                <strong>{t(`compare.${side}`)}</strong>
                <p>
                  {t("new.totalTokens")}: {formatTokens(usage?.[side]?.total_tokens, t("cost.unknown"))}
                  {" · "}{t("dashboard.metric.cost")}: {formatCost(usage?.[side]?.cost_usd, usage?.[side]?.cost_status, t("cost.unknown"))}
                  {" · "}{presentCostStatus(usage?.[side]?.cost_status, locale)}
                </p>
              </div>
            ))}
          </article>
        </div>
      ) : null}
    </div>
  );
}
