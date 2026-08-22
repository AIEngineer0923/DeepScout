"use client";

import { useMemo, useState } from "react";
import type { Workspace } from "@/lib/types";
import { relativeTime } from "@/lib/format";
import { useI18n } from "@/i18n/context";
import { eventMatchesFilter, isLowValueTimelineEvent, presentEvent } from "@/presentation/events";

const FILTERS = ["all", "phase", "worker", "source", "evidence", "quality", "report"] as const;

export function ResearchTimeline({
  workspace,
  completed,
}: {
  workspace: Workspace;
  completed: boolean;
}) {
  const { t, locale } = useI18n();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");

  const events = useMemo(() => {
    const rows = [...workspace.activity].reverse().filter((event) => !isLowValueTimelineEvent(event.type));
    const filtered = rows.filter((event) => eventMatchesFilter(event.type, filter));
    const seen = new Set<string>();
    const deduped = [];
    for (const event of filtered) {
      const key = `${event.type}:${JSON.stringify(event.payload?.phase ?? "")}`;
      if (seen.has(key) && (event.type === "phase.started" || event.type === "phase.completed")) {
        continue;
      }
      seen.add(key);
      deduped.push(event);
      if (deduped.length >= 16) break;
    }
    return deduped;
  }, [workspace.activity, filter]);

  return (
    <section className="card research-timeline" data-testid="research-timeline">
      <div className="card-head">
        <div>
          <h2>{completed ? t("demo.timeline.completed") : t("live.activity")}</h2>
          <p className="muted timeline-sub">{completed ? t("demo.timeline.completedSub") : t("live.activitySub")}</p>
        </div>
      </div>
      <div className="activity-tabs" role="group" aria-label={t("demo.timeline.filters")}>
        {FILTERS.map((item) => (
          <button
            key={item}
            type="button"
            className={`activity-tab ${filter === item ? "active" : ""}`}
            aria-pressed={filter === item}
            onClick={() => setFilter(item)}
          >
            {t(`activity.${item}`)}
          </button>
        ))}
      </div>
      <ol className="timeline-list">
        {events.map((event) => {
          const presented = presentEvent(event.type, locale, event.payload ?? {}, workspace);
          return (
            <li key={event.sequence} className="timeline-item">
              <span className={`timeline-icon cat-${presented.category}`} aria-hidden="true">
                {presented.icon}
              </span>
              <div className="timeline-body">
                <strong>{presented.label}</strong>
                {presented.detail ? <div className="muted timeline-detail">{presented.detail}</div> : null}
              </div>
              <time className="muted timeline-time">{relativeTime(event.created_at, locale)}</time>
            </li>
          );
        })}
      </ol>
      {events.length === 0 ? <p className="empty">{t("live.waiting")}</p> : null}
    </section>
  );
}
