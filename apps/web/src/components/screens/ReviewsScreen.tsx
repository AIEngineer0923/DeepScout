"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { useT } from "@/i18n/context";

type Review = {
  id: string;
  research_run_id: string;
  reason_code: string;
  risk_level: string;
  title: string;
  explanation: string;
  proposed_action_type: string;
  proposed_action_payload: Record<string, number | string>;
  status: string;
  expires_at?: string | null;
};

export function ReviewsScreen() {
  const t = useT();
  const [items, setItems] = useState<Review[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .listReviews("pending")
      .then((rows) => setItems(rows as Review[]))
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function act(review: Review, kind: "approve" | "reject" | "edit") {
    setBusy(review.id);
    setError(null);
    try {
      if (kind === "approve") {
        await api.approveReview(review.research_run_id, review.id);
      } else if (kind === "reject") {
        await api.rejectReview(review.research_run_id, review.id, {
          outcome: "STOP_AND_SYNTHESIZE",
        });
      } else {
        const payload = review.proposed_action_payload;
        await api.editReview(review.research_run_id, review.id, {
          requested_extra_iterations: Number(payload.requested_extra_iterations ?? 1),
          requested_extra_tool_calls: Number(payload.requested_extra_tool_calls ?? 5),
          requested_extra_sources: Number(payload.requested_extra_sources ?? 2),
        });
      }
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <h1 className="page-title">{t("reviews.title")}</h1>
      <p className="page-sub">{t("reviews.subtitle")}</p>
      {error ? <p className="error" role="alert">{error}</p> : null}
      {items.length === 0 ? <p className="empty">{t("reviews.empty")}</p> : null}
      <div className="stack" style={{ gap: 16, marginTop: 16 }}>
        {items.map((review) => {
          const p = review.proposed_action_payload;
          return (
            <article key={review.id} className="card" aria-labelledby={`review-${review.id}`}>
              <div className="row" style={{ justifyContent: "space-between", gap: 12 }}>
                <h2 id={`review-${review.id}`}>{review.title}</h2>
                <StatusBadge status={review.status} />
              </div>
              <p className="wrap-text">{review.explanation}</p>
              <p className="muted">
                {t("reviews.risk")}: {review.risk_level} · {review.reason_code.replaceAll("_", " ")}
              </p>
              {review.proposed_action_type === "budget_extension" ? (
                <div className="grid cols-3" style={{ margin: "12px 0" }}>
                  <div>
                    <strong>{t("reviews.currentLimits")}</strong>
                    <p>
                      iter {String(p.current_max_iterations)} / tools {String(p.current_max_tool_calls)} / sources{" "}
                      {String(p.current_max_sources)}
                    </p>
                  </div>
                  <div>
                    <strong>{t("reviews.requested")}</strong>
                    <p>
                      +{String(p.requested_extra_iterations)} iter · +{String(p.requested_extra_tool_calls)} tools · +
                      {String(p.requested_extra_sources)} sources
                    </p>
                  </div>
                  <div>
                    <strong>{t("reviews.consumed")}</strong>
                    <p>
                      {String(p.consumed_iterations)} iter · cost {String(p.consumed_cost_usd)} ({String(p.cost_status)})
                    </p>
                  </div>
                </div>
              ) : null}
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                <button
                  className="btn primary"
                  disabled={busy === review.id}
                  onClick={() => void act(review, "approve")}
                >
                  {t("reviews.approve")}
                </button>
                <button className="btn" disabled={busy === review.id} onClick={() => void act(review, "edit")}>
                  {t("reviews.editSmaller")}
                </button>
                <button className="btn danger" disabled={busy === review.id} onClick={() => void act(review, "reject")}>
                  {t("reviews.reject")}
                </button>
                <Link className="btn" href={`/research/${review.research_run_id}`}>
                  {t("reviews.openRun")}
                </Link>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
