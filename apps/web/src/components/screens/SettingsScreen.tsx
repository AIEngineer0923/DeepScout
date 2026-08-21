"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Tabs } from "@/components/Tabs";
import { useI18n } from "@/i18n/context";

export function SettingsScreen() {
  const { t, locale, setLocale } = useI18n();
  const [tab, setTab] = useState("general");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    api.settings().then(setData).catch(() => setData(null));
  }, []);
  const providers = (data?.providers ?? {}) as Record<string, { configured?: boolean; model?: string }>;
  const langsmith = (data?.langsmith ?? {}) as { connected?: boolean; project?: string; region?: string };
  const defaults = (data?.research_defaults ?? {}) as Record<string, unknown>;
  const health = (data?.health ?? {}) as Record<string, string>;
  const identity = (data?.identity ?? {}) as { label?: string; role?: string };
  const tabs = [
    { id: "general", label: t("settings.tab.general") },
    { id: "models", label: t("settings.tab.models") },
    { id: "research", label: t("settings.tab.research") },
    { id: "quality", label: t("settings.tab.quality") },
    { id: "integrations", label: t("settings.tab.integrations") },
    { id: "security", label: t("settings.tab.security") },
    { id: "notifications", label: t("settings.tab.notifications") },
    { id: "advanced", label: t("settings.tab.advanced") },
  ];
  return (
    <div>
      <h1 className="page-title">{t("settings.title")}</h1>
      <p className="page-sub">{t("settings.subtitle")}</p>
      <Tabs items={tabs} value={tab} onChange={setTab} ariaLabel={t("settings.title")} />
      <div className="grid cols-2">
        <section className="card">
          {tab === "general" ? (
            <>
              <h2>{t("settings.workspace")}</h2>
              <p>
                {identity.label} · {identity.role}
              </p>
              <div className="field" style={{ marginTop: 12 }}>
                <label htmlFor="ui-lang">{t("settings.uiLanguage")}</label>
                <select id="ui-lang" className="select" value={locale} onChange={(e) => setLocale(e.target.value === "it" ? "it" : "en")} data-testid="settings-ui-language">
                  <option value="en">{t("uiLanguage.en")}</option>
                  <option value="it">{t("uiLanguage.it")}</option>
                </select>
              </div>
              <p className="muted">{t("settings.researchLangNote")}</p>
              <p className="muted">{t("settings.noMultiuser")}</p>
            </>
          ) : null}
          {tab === "models" ? (
            <>
              <h2>{t("settings.providers")}</h2>
              {Object.entries(providers).map(([name, value]) => (
                <p key={name}>
                  {name}: {value.configured ? t("configured") : t("notConfigured")}
                  {value.model ? ` · ${value.model}` : ""}
                </p>
              ))}
              <p className="muted">{t("settings.keysHidden")}</p>
              <h2>{t("settings.routing")}</h2>
              <p>{t("settings.routingAuto")}</p>
            </>
          ) : null}
          {tab === "research" ? (
            <>
              <h2>{t("settings.researchDefaults")}</h2>
              <p>
                {t("provider.maxIterations")}: {String(defaults.max_iterations)}
              </p>
              <p>
                {t("provider.maxSources")}: {String(defaults.max_sources)}
              </p>
              <p>
                {t("settings.maxToolCalls")}: {String(defaults.max_tool_calls)}
              </p>
              <p>
                {t("settings.durableCheckpoint")}: {String(defaults.durable_checkpoint)}
              </p>
              <p className="muted">{String(defaults.concurrency_note)}</p>
            </>
          ) : null}
          {tab === "quality" ? (
            <>
              <h2>{t("settings.evals")}</h2>
              <p>{t("settings.evalsDet")}</p>
              <p>{t("settings.evalsLlm")}</p>
            </>
          ) : null}
          {tab === "integrations" ? (
            <>
              <h2>LangSmith</h2>
              <p>
                {t("table.status")}: {langsmith.connected ? t("langsmith.connected") : t("langsmith.notConfigured")}
              </p>
              <p>
                {t("settings.project")}: {langsmith.project}
              </p>
              <p>
                {t("settings.region")}: {langsmith.region}
              </p>
            </>
          ) : null}
          {tab === "security" ? (
            <>
              <h2>{t("settings.privacy")}</h2>
              <p>{String((data?.security as { untrusted_content?: string } | undefined)?.untrusted_content)}</p>
              <p>{String((data?.security as { ssrf?: string } | undefined)?.ssrf)}</p>
            </>
          ) : null}
          {tab === "notifications" ? <p className="muted">{t("settings.notifications")}</p> : null}
          {tab === "advanced" ? (
            <>
              <h2>{t("settings.system")}</h2>
              {Object.entries(health).map(([key, value]) => (
                <p key={key}>
                  {key}: {value}
                </p>
              ))}
              <p className="muted">{t("settings.vector")}</p>
            </>
          ) : null}
        </section>
        <aside className="drawer">
          <h2>{t("settings.system")}</h2>
          {Object.entries(health).map(([key, value]) => (
            <p key={key}>
              {key}: {value}
            </p>
          ))}
          <p className="muted">{t("settings.noSaas")}</p>
        </aside>
      </div>
    </div>
  );
}
