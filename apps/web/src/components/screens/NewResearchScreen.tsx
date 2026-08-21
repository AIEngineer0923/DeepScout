"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { COUNTRY_OPTIONS, countryLabel } from "@/lib/countries";
import { rememberRunId } from "@/lib/current-run";
import { useI18n, useT } from "@/i18n/context";
import { IconBolt, IconCheck, IconLayers, IconSpark } from "@/components/Icons";

type Template = {
  id: string;
  name: string;
  goal: string;
  research_mode: "quick" | "standard" | "deep";
  output_language: string;
};

type ModelPolicyMode = "automatic" | "quality" | "balanced" | "speed" | "cost" | "manual";
type GeoMode = "automatic" | "global" | "regions";
type FreshnessMode = "automatic" | "explicit";
type FreshnessPolicy = "any" | "24h" | "7d" | "30d" | "1y";

const MODES = [
  { id: "quick" as const, titleKey: "new.mode.quick", bodyKey: "new.mode.quickBody", badgeKey: "new.mode.quickBadge", icon: IconBolt },
  { id: "standard" as const, titleKey: "new.mode.standard", bodyKey: "new.mode.standardBody", badgeKey: "new.mode.standardBadge", icon: IconLayers },
  { id: "deep" as const, titleKey: "new.mode.deep", bodyKey: "new.mode.deepBody", badgeKey: "new.mode.deepBadge", icon: IconSpark },
];

function parseDomains(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function NewResearchScreen() {
  const router = useRouter();
  const t = useT();
  const { locale } = useI18n();
  const [goal, setGoal] = useState("");
  const [mode, setMode] = useState<"quick" | "standard" | "deep">("standard");
  const [outputLanguage, setOutputLanguage] = useState(locale === "it" ? "it" : "en");
  const [modelPolicy, setModelPolicy] = useState<ModelPolicyMode>("automatic");
  const [geoMode, setGeoMode] = useState<GeoMode>("automatic");
  const [geoRegions, setGeoRegions] = useState<string[]>([]);
  const [geoQuery, setGeoQuery] = useState("");
  const [freshnessMode, setFreshnessMode] = useState<FreshnessMode>("automatic");
  const [freshnessPolicy, setFreshnessPolicy] = useState<FreshnessPolicy>("any");
  const [excludedDomains, setExcludedDomains] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templateName, setTemplateName] = useState("");
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [providerReady, setProviderReady] = useState(true);
  const [hosted, setHosted] = useState(false);

  useEffect(() => {
    api.listTemplates().then(setTemplates).catch(() => setTemplates([]));
    Promise.all([api.settings(), api.me().catch(() => ({ mode: "local" }))])
      .then(([settings, me]) => {
        const identity = settings.identity as { mode?: string } | undefined;
        const isHosted = me.mode === "hosted" || identity?.mode === "hosted";
        setHosted(isHosted);
        if (!isHosted) {
          setProviderReady(true);
          return;
        }
        const providers = settings.providers as Record<string, { configured?: boolean }>;
        const llmReady = Boolean(providers.google?.configured || providers.openai?.configured || providers.anthropic?.configured);
        const searchReady = Boolean(providers.tavily?.configured);
        setProviderReady(llmReady && searchReady);
      })
      .catch(() => setProviderReady(true));
  }, []);

  const filteredCountries = useMemo(() => {
    const q = geoQuery.trim().toLowerCase();
    if (!q) return COUNTRY_OPTIONS;
    return COUNTRY_OPTIONS.filter(
      (item) =>
        item.en.toLowerCase().includes(q) ||
        item.it.toLowerCase().includes(q) ||
        item.code.toLowerCase().includes(q),
    );
  }, [geoQuery]);

  const summary = useMemo(
    () => ({
      mode,
      outputLanguage,
      sources: mode === "quick" ? "4–8" : mode === "deep" ? "20–60" : "8–20",
      iterations: mode === "quick" ? "1" : mode === "deep" ? "Up to 5" : "Up to 3",
      depth: mode === "quick" ? t("new.depthQuick") : mode === "deep" ? t("new.depthDeep") : t("new.depthStandard"),
    }),
    [mode, outputLanguage, t],
  );

  function buildPreferences() {
    return {
      geographic_focus: {
        mode: geoMode,
        regions: geoMode === "regions" ? geoRegions : [],
      },
      freshness: {
        mode: freshnessMode,
        policy: freshnessMode === "automatic" ? "any" : freshnessPolicy,
      },
      model_policy: { mode: modelPolicy, provider: null, model: null },
      excluded_domains: parseDomains(excludedDomains),
    };
  }

  async function refreshTemplates() {
    try {
      setTemplates(await api.listTemplates());
    } catch {
      setTemplates([]);
    }
  }

  async function saveTemplate() {
    if (!goal.trim()) {
      setError(t("new.templateNeedGoal"));
      return;
    }
    if (!templateName.trim()) {
      setError(t("new.templateNeedName"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.createTemplate({
        name: templateName.trim(),
        goal: goal.trim(),
        research_mode: mode,
        output_language: outputLanguage,
      });
      setTemplateName("");
      setShowTemplateDialog(false);
      setNotice(t("new.templateSaved"));
      await refreshTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("new.startError"));
    } finally {
      setSaving(false);
    }
  }

  function applyTemplate(item: Template) {
    setGoal(item.goal);
    setMode(item.research_mode);
    setOutputLanguage(item.output_language === "it" ? "it" : "en");
    setNotice(null);
    setError(null);
  }

  async function removeTemplate(id: string) {
    try {
      await api.deleteTemplate(id);
      await refreshTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("new.startError"));
    }
  }

  function toggleRegion(name: string) {
    setGeoRegions((current) =>
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name],
    );
  }

  async function start() {
    if (!goal.trim()) return;
    if (hosted && !providerReady) {
      setError(t("new.providerMissing"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api.createRun({
        goal: goal.trim(),
        research_mode: mode,
        output_language: outputLanguage,
        preferences: buildPreferences(),
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
    <div className="grid cols-form">
      <div>
        <div className="page-head">
          <h1 className="page-title">{t("new.title")}</h1>
          <p className="page-sub">{t("new.subtitle")}</p>
        </div>
        <div className="card" style={{ marginTop: 18 }}>
          <div className="field">
            <label htmlFor="goal" className="section-title">
              <span className="section-num" aria-hidden="true">
                1
              </span>
              {t("new.step1")}
            </label>
            <textarea
              id="goal"
              className="textarea"
              style={{ minHeight: 128 }}
              maxLength={8000}
              placeholder={t("new.goalPlaceholder")}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              data-testid="research-goal"
            />
            <span className="muted">{goal.length} / 8000</span>
          </div>
          <div style={{ marginTop: 20 }}>
            <div className="section-title">
              <span className="section-num">2</span>
              {t("new.step2")}
            </div>
            <div className="mode-grid" style={{ marginTop: 4 }} role="radiogroup" aria-label={t("new.step2")}>
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
          <div style={{ marginTop: 20 }}>
            <div className="section-title">
              <span className="section-num">3</span>
              {t("new.step3")}
            </div>
            <div className="grid cols-2" style={{ marginTop: 4 }}>
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
                <label htmlFor="model-policy">{t("new.modelPolicy")}</label>
                <select
                  id="model-policy"
                  className="select"
                  value={modelPolicy}
                  onChange={(e) => setModelPolicy(e.target.value as ModelPolicyMode)}
                  data-testid="model-policy"
                >
                  <option value="automatic">{t("new.model.automatic")}</option>
                  <option value="quality">{t("new.model.quality")}</option>
                  <option value="balanced">{t("new.model.balanced")}</option>
                  <option value="speed">{t("new.model.speed")}</option>
                  <option value="cost">{t("new.model.cost")}</option>
                </select>
                <span className="muted">{t("new.modelPolicyHelp")}</span>
              </div>
              <div className="field">
                <label htmlFor="geo-mode">{t("new.region")}</label>
                <select
                  id="geo-mode"
                  className="select"
                  value={geoMode}
                  onChange={(e) => setGeoMode(e.target.value as GeoMode)}
                  data-testid="geo-mode"
                >
                  <option value="automatic">{t("new.geo.automatic")}</option>
                  <option value="global">{t("new.geo.global")}</option>
                  <option value="regions">{t("new.geo.regions")}</option>
                </select>
                {geoMode === "regions" ? (
                  <div style={{ marginTop: 8 }}>
                    <input
                      className="input"
                      placeholder={t("new.geo.search")}
                      value={geoQuery}
                      onChange={(e) => setGeoQuery(e.target.value)}
                      aria-label={t("new.geo.search")}
                    />
                    <div className="chip-row" style={{ marginTop: 8 }}>
                      {filteredCountries.map((item) => {
                        const label = countryLabel(item.en, locale);
                        const selected = geoRegions.includes(item.en);
                        return (
                          <button
                            key={item.code}
                            type="button"
                            className={`chip ${selected ? "selected" : ""}`}
                            onClick={() => toggleRegion(item.en)}
                          >
                            {label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
                <span className="muted">{t("new.geo.regionsHelp")}</span>
              </div>
              <div className="field">
                <label htmlFor="freshness">{t("new.freshness")}</label>
                <select
                  id="freshness"
                  className="select"
                  value={freshnessMode === "automatic" ? "automatic" : freshnessPolicy}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === "automatic") {
                      setFreshnessMode("automatic");
                    } else {
                      setFreshnessMode("explicit");
                      setFreshnessPolicy(value as FreshnessPolicy);
                    }
                  }}
                  data-testid="freshness-policy"
                >
                  <option value="automatic">{t("new.freshness.automatic")}</option>
                  <option value="any">{t("new.freshness.any")}</option>
                  <option value="24h">{t("new.freshness.24h")}</option>
                  <option value="7d">{t("new.freshness.7d")}</option>
                  <option value="30d">{t("new.freshness.30d")}</option>
                  <option value="1y">{t("new.freshness.1y")}</option>
                </select>
                <span className="muted">{t("new.freshnessHelp")}</span>
              </div>
            </div>
          </div>
          <button type="button" className="btn ghost" style={{ marginTop: 16 }} onClick={() => setAdvanced(!advanced)}>
            {advanced ? t("action.hideAdvanced") : t("action.showAdvanced")}
          </button>
          {advanced ? (
            <div className="field" style={{ marginTop: 8 }}>
              <label htmlFor="excluded">{t("new.excluded")}</label>
              <input
                id="excluded"
                className="input"
                value={excludedDomains}
                onChange={(e) => setExcludedDomains(e.target.value)}
                placeholder={t("new.excludedPlaceholder")}
                data-testid="excluded-domains"
              />
              <span className="muted">{t("new.excludedHelp")}</span>
              <label htmlFor="max-sources" style={{ marginTop: 12, display: "block" }}>
                {t("new.maxSources")}
              </label>
              <input id="max-sources" className="input" value={summary.sources} readOnly title={t("new.budgetByMode")} />
              <span className="muted">{t("new.budgetByMode")}</span>
            </div>
          ) : null}
          {hosted && !providerReady ? (
            <div className="note-box" style={{ marginTop: 12 }}>
              <p className="wrap-text" style={{ margin: 0 }}>
                {t("new.providerMissing")}
              </p>
              <button type="button" className="btn" style={{ marginTop: 8 }} onClick={() => router.push("/account")}>
                {t("new.configureProviders")}
              </button>
            </div>
          ) : null}
          {error ? <p className="badge bad wrap-text">{error}</p> : null}
          {notice ? <p className="badge ok wrap-text">{notice}</p> : null}
          <div className="form-actions" style={{ marginTop: 18 }}>
            <button className="btn ghost" type="button" onClick={() => router.push("/dashboard")}>
              {t("action.cancel")}
            </button>
            <div className="row">
              <button className="btn" type="button" onClick={() => setShowTemplateDialog(true)} disabled={!goal.trim()}>
                {t("new.saveTemplate")}
              </button>
              <button
                className="btn primary"
                type="button"
                disabled={busy || !goal.trim() || (hosted && !providerReady)}
                data-testid="start-research"
                onClick={() => void start()}
              >
                {t("action.start")} →
              </button>
            </div>
          </div>
        </div>
        {showTemplateDialog ? (
          <div className="card" style={{ marginTop: 16 }} role="dialog" aria-labelledby="template-dialog-title">
            <h2 id="template-dialog-title">{t("new.saveTemplateTitle")}</h2>
            <div className="field">
              <label htmlFor="template-name">{t("new.templateNameLabel")}</label>
              <input
                id="template-name"
                className="input"
                maxLength={80}
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                data-testid="template-name"
              />
            </div>
            <div className="row" style={{ marginTop: 12 }}>
              <button type="button" className="btn ghost" onClick={() => setShowTemplateDialog(false)}>
                {t("action.cancel")}
              </button>
              <button
                type="button"
                className="btn primary"
                disabled={saving || !templateName.trim()}
                data-testid="save-template"
                onClick={() => void saveTemplate()}
              >
                {t("action.save")}
              </button>
            </div>
          </div>
        ) : null}
      </div>
      <aside>
        <section className="card">
          <h2>{t("new.summary")}</h2>
          <p className="wrap-text muted">{goal || t("new.summaryEmpty")}</p>
          <dl className="kv-list" style={{ marginTop: 12 }}>
            <div className="kv-row">
              <dt>{t("new.step2")}</dt>
              <dd>
                <span className="badge run" data-testid="summary-mode" data-value={summary.mode}>
                  {t(`new.mode.${summary.mode}`)}
                </span>
              </dd>
            </div>
            <div className="kv-row">
              <dt>{t("new.expectedDepth")}</dt>
              <dd>{summary.depth}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("new.expectedSources")}</dt>
              <dd>{summary.sources}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("new.maxIterations")}</dt>
              <dd>{summary.iterations}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("new.outputLanguage")}</dt>
              <dd>{summary.outputLanguage === "it" ? t("lang.it") : t("lang.en")}</dd>
            </div>
          </dl>
        </section>
        <section className="card" style={{ marginTop: 16 }}>
          <h2>{t("new.estimatedEnvelope")}</h2>
          <dl className="kv-list">
            <div className="kv-row">
              <dt>{t("new.modelCalls")}</dt>
              <dd>{mode === "quick" ? "~3–6" : mode === "deep" ? "~12–24" : "~7–12"}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("new.totalTokens")}</dt>
              <dd>{mode === "quick" ? "~8k–20k" : mode === "deep" ? "~60k–150k" : "~25k–60k"}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("new.toolCalls")}</dt>
              <dd>{mode === "quick" ? "~6–12" : mode === "deep" ? "~30–60" : "~15–25"}</dd>
            </div>
            <div className="kv-row">
              <dt>{t("new.duration")}</dt>
              <dd>{mode === "quick" ? "~1–2 min" : mode === "deep" ? "~5–12 min" : "~2–5 min"}</dd>
            </div>
          </dl>
          <div className="cost-highlight">{t("new.costUnknown")}</div>
          <p className="cost-range">{t("new.actualUsage")}</p>
        </section>
        <section className="card" style={{ marginTop: 16 }}>
          <h2>{t("new.templates")}</h2>
          {templates.length === 0 ? (
            <p className="muted wrap-text">{t("new.templatesEmpty")}</p>
          ) : (
            <ul className="kv-list" style={{ marginTop: 8 }} data-testid="template-list">
              {templates.map((item) => (
                <li key={item.id} className="kv-row" style={{ alignItems: "flex-start", gap: 8 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <strong className="wrap-text">{item.name}</strong>
                    <div className="muted wrap-text">{item.goal}</div>
                    <div className="muted">{item.research_mode}</div>
                  </div>
                  <div className="row">
                    <button type="button" className="btn" data-testid={`apply-template-${item.id}`} onClick={() => applyTemplate(item)}>
                      {t("new.templateApply")}
                    </button>
                    <button type="button" className="btn ghost" onClick={() => void removeTemplate(item.id)}>
                      {t("new.templateDelete")}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>
    </div>
  );
}
