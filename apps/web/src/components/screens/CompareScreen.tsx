"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";

export function CompareScreen() {
  const t = useT();
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
            <p>{t("compare.left")}: {String((diff.left as { goal?: string })?.goal)}</p>
            <p>{t("compare.right")}: {String((diff.right as { goal?: string })?.goal)}</p>
            <p>{t("nav.plan")}: {JSON.stringify((diff.plan as { left?: { task_count?: number }; right?: { task_count?: number } }) ?? {})}</p>
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
            <p>L tokens: {usage?.left?.total_tokens ?? t("cost.unknown")} · {usage?.left?.cost_status}</p>
            <p>R tokens: {usage?.right?.total_tokens ?? t("cost.unknown")} · {usage?.right?.cost_status}</p>
          </article>
        </div>
      ) : null}
    </div>
  );
}
