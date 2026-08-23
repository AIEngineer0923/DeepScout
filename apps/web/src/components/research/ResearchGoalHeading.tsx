"use client";

import { useId, useState } from "react";
import type { Workspace } from "@/lib/types";
import type { Locale } from "@/i18n/messages";
import { useT } from "@/i18n/context";
import { displayGoal } from "@/presentation/demo";
import { displayResearchTitle, normalizeResearchText } from "@/presentation/research";

export function ResearchGoalHeading({
  workspace,
  locale,
  level = 1,
  className = "research-title",
}: {
  workspace: Workspace;
  locale: Locale;
  level?: 1 | 2;
  className?: string;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const detailsId = useId();
  const Heading = level === 1 ? "h1" : "h2";
  const goal = displayGoal(workspace, locale).trim();
  const title = displayResearchTitle(workspace, locale);
  const hasDetails = normalizeResearchText(goal) !== normalizeResearchText(title);

  return (
    <div className="research-goal-block">
      <Heading className={className} data-testid="research-title">
        {title}
      </Heading>
      {hasDetails ? (
        <>
          <button
            type="button"
            className="research-goal-toggle"
            aria-expanded={open}
            aria-controls={detailsId}
            onClick={() => setOpen((value) => !value)}
          >
            <span className={`research-goal-chevron ${open ? "open" : ""}`} aria-hidden="true">
              ›
            </span>
            {open ? t("research.request.hide") : t("research.request.show")}
          </button>
          {open ? (
            <div id={detailsId} className="research-goal-details" data-testid="research-goal-details">
              <p>{goal}</p>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
