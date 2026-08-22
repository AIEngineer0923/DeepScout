"use client";

import { useState } from "react";
import type { Workspace } from "@/lib/types";
import { formatCost, formatTokens } from "@/lib/format";
import { useI18n, useT } from "@/i18n/context";
import { presentOutputLanguage } from "@/presentation/fields";

export function TechnicalDetails({ workspace }: { workspace: Workspace }) {
  const t = useT();
  const { locale } = useI18n();
  const [open, setOpen] = useState(false);

  return (
    <section className="technical-details" data-testid="technical-details">
      <button
        type="button"
        className="technical-details-toggle"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span>{t("demo.technicalDetails")}</span>
        <span aria-hidden="true">{open ? "−" : "+"}</span>
      </button>
      {open ? (
        <dl className="technical-details-grid">
          <div>
            <dt>{t("provider.provider")}</dt>
            <dd>{workspace.llm_provider}</dd>
          </div>
          <div>
            <dt>{t("provider.model")}</dt>
            <dd>{workspace.llm_model}</dd>
          </div>
          <div>
            <dt>{t("provider.tokens")}</dt>
            <dd>{formatTokens(workspace.usage.total_tokens, t("cost.unknown"))}</dd>
          </div>
          <div>
            <dt>{t("provider.appCost")}</dt>
            <dd>{formatCost(workspace.usage.cost_usd, workspace.usage.cost_status, t("cost.unknown"))}</dd>
          </div>
          <div>
            <dt>{t("provider.evalCost")}</dt>
            <dd>
              {formatCost(
                workspace.usage.evaluation_cost_usd,
                workspace.usage.evaluation_cost_usd == null ? "unknown" : "estimated",
                t("cost.unknown"),
              )}
            </dd>
          </div>
          <div>
            <dt>{t("demo.runId")}</dt>
            <dd className="mono">{workspace.run_id}</dd>
          </div>
          {workspace.output_language ? (
            <div>
              <dt>{t("new.outputLanguage")}</dt>
              <dd>{presentOutputLanguage(workspace.output_language, locale)}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
    </section>
  );
}
