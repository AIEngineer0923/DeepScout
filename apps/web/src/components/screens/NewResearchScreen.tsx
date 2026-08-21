"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { rememberRunId } from "@/lib/current-run";
import { useT } from "@/i18n/context";
import { IconBolt, IconCheck, IconLayers, IconSpark } from "@/components/Icons";

const MODES = [
  { id: "quick" as const, titleKey: "new.mode.quick", bodyKey: "new.mode.quickBody", badgeKey: "new.mode.quickBadge", icon: IconBolt },
  { id: "standard" as const, titleKey: "new.mode.standard", bodyKey: "new.mode.standardBody", badgeKey: "new.mode.standardBadge", icon: IconLayers },
  { id: "deep" as const, titleKey: "new.mode.deep", bodyKey: "new.mode.deepBody", badgeKey: "new.mode.deepBadge", icon: IconSpark },
];

export function NewResearchScreen() {
  const router = useRouter();
  const t = useT();
  const [goal, setGoal] = useState("");
  const [mode, setMode] = useState<"quick" | "standard" | "deep">("standard");
  const [outputLanguage, setOutputLanguage] = useState("en");
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const summary = useMemo(
    () => ({
      mode,
      outputLanguage,
      sources: mode === "quick" ? "4–8" : mode === "deep" ? "20–60" : "8–20",
    }),
    [mode, outputLanguage],
  );

  async function start() {
    if (!goal.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.createRun({
        goal: goal.trim(),
        research_mode: mode,
        output_language: outputLanguage,
      });
      rememberRunId(created.id);
      await api.execute(created.id);
      router.push(`/research/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("new.startError"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid cols-2">
      <div>
        <h1 className="page-title">{t("new.title")}</h1>
        <p className="page-sub">{t("new.subtitle")}</p>
        <div className="card" style={{ marginTop: 16 }}>
          <div className="field">
            <label htmlFor="goal">{t("new.step1")}</label>
            <textarea
              id="goal"
              className="textarea"
              maxLength={1000}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              data-testid="research-goal"
            />
            <span className="muted">{goal.length} / 1000</span>
          </div>
          <div style={{ marginTop: 16 }}>
            <div className="muted">{t("new.step2")}</div>
            <div className="mode-grid" style={{ marginTop: 8 }} role="radiogroup" aria-label={t("new.step2")}>
              {MODES.map((item) => {
                const selected = mode === item.id;
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    data-testid={`mode-${item.id}`}
                    className={`mode ${selected ? "selected" : ""}`}
                    onClick={() => setMode(item.id)}
                  >
                    {selected ? (
                      <span className="mode-check">
                        <IconCheck />
                      </span>
                    ) : null}
                    <span className="mode-icon">
                      <Icon />
                    </span>
                    <strong>{t(item.titleKey)}</strong>
                    <div className="muted">{t(item.bodyKey)}</div>
                    <span className="mode-badge">{t(item.badgeKey)}</span>
                  </button>
                );
              })}
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <div className="muted">{t("new.step3")}</div>
            <div className="grid cols-2" style={{ marginTop: 8 }}>
              <div className="field">
                <label htmlFor="output-language">{t("new.outputLanguage")}</label>
                <select
                  id="output-language"
                  className="select"
                  value={outputLanguage}
                  onChange={(e) => setOutputLanguage(e.target.value)}
                  data-testid="output-language"
                >
                  <option value="en">{t("lang.en")}</option>
                  <option value="it">{t("lang.it")}</option>
                </select>
                <span className="muted">{t("new.outputLanguageHelp")}</span>
              </div>
              <div className="field">
                <label htmlFor="freshness">{t("new.freshness")}</label>
                <select id="freshness" className="select" disabled aria-disabled="true" title={t("new.unsupportedFilter")}>
                  <option>{t("freshness.live")}</option>
                </select>
                <span className="muted">{t("new.unsupportedFilter")}</span>
              </div>
              <div className="field">
                <label htmlFor="excluded">{t("new.excluded")}</label>
                <input id="excluded" className="input" disabled aria-disabled="true" placeholder="—" title={t("new.unsupportedFilter")} />
                <span className="muted">{t("new.unsupportedFilter")}</span>
              </div>
              <div className="field">
                <label htmlFor="region">{t("new.region")}</label>
                <input id="region" className="input" value={t("new.regionAny")} readOnly title={t("new.unsupportedFilter")} />
                <span className="muted">{t("new.unsupportedFilter")}</span>
              </div>
            </div>
          </div>
          <button type="button" className="btn ghost" style={{ marginTop: 12 }} onClick={() => setAdvanced(!advanced)}>
            {advanced ? t("action.hideAdvanced") : t("action.showAdvanced")}
          </button>
          {advanced ? (
            <div className="field" style={{ marginTop: 8 }}>
              <label htmlFor="max-sources">{t("new.maxSources")}</label>
              <input id="max-sources" className="input" value={summary.sources} readOnly title={t("new.budgetByMode")} />
              <span className="muted">{t("new.budgetByMode")}</span>
            </div>
          ) : null}
          {error ? <p className="badge bad wrap-text">{error}</p> : null}
          <div className="form-actions" style={{ marginTop: 16 }}>
            <button className="btn" type="button" onClick={() => router.push("/")}>
              {t("action.cancel")}
            </button>
            <button className="btn primary" type="button" disabled={busy || !goal.trim()} data-testid="start-research" onClick={() => void start()}>
              {t("action.start")} →
            </button>
          </div>
        </div>
      </div>
      <aside>
        <section className="card">
          <h2>{t("new.summary")}</h2>
          <p className="wrap-text">{goal || t("new.summaryEmpty")}</p>
          <p>
            {t("new.step2")}: <strong data-testid="summary-mode">{summary.mode}</strong>
          </p>
          <p>
            {t("new.expectedSources")}: {summary.sources}
          </p>
          <p>
            {t("new.outputLanguage")}: {summary.outputLanguage === "it" ? t("lang.it") : t("lang.en")}
          </p>
        </section>
        <section className="card" style={{ marginTop: 16 }}>
          <h2>{t("new.resources")}</h2>
          <p>
            {t("provider.appCost")}: <strong>{t("new.costUnknown")}</strong>
          </p>
          <p className="muted">{t("new.costNote")}</p>
        </section>
      </aside>
    </div>
  );
}
