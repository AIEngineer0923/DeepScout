"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { parseRunId, readLastRunId, rememberRunId } from "@/lib/current-run";
import { initials } from "@/lib/visual";
import { useI18n } from "@/i18n/context";
import {
  IconClaims,
  IconEvals,
  IconHistory,
  IconHome,
  IconLive,
  IconPlan,
  IconPlus,
  IconQuality,
  IconReport,
  IconResume,
  IconSettings,
  IconSnapshot,
  IconSources,
  IconWorkers,
} from "./Icons";

const RESEARCH = [
  { id: "live", icon: IconLive },
  { id: "plan", icon: IconPlan },
  { id: "workers", icon: IconWorkers },
  { id: "sources", icon: IconSources },
  { id: "snapshot", icon: IconSnapshot },
  { id: "claims", icon: IconClaims },
  { id: "quality", icon: IconQuality },
  { id: "report", icon: IconReport },
  { id: "evaluations", icon: IconEvals },
] as const;

function hrefFor(item: (typeof RESEARCH)[number]["id"], runId: string) {
  if (item === "live") return `/research/${runId}`;
  if (item === "snapshot") return `/research/${runId}/snapshots`;
  return `/research/${runId}/${item}`;
}

function isCurrent(item: (typeof RESEARCH)[number]["id"], pathname: string, runId: string | null) {
  if (!runId) return false;
  if (item === "live") return pathname === `/research/${runId}`;
  if (item === "snapshot") return pathname.includes("/snapshots");
  return pathname.startsWith(`/research/${runId}/${item}`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t, locale, setLocale } = useI18n();
  const pathRunId = parseRunId(pathname);
  const [storedRunId, setStoredRunId] = useState<string | null>(null);
  const [langsmith, setLangsmith] = useState<{ connected: boolean; project: string; region: string } | null>(null);
  const [identityLabel, setIdentityLabel] = useState("Local workspace");
  const [identityRole, setIdentityRole] = useState("Operator");

  useEffect(() => {
    if (pathRunId) rememberRunId(pathRunId);
    setStoredRunId(pathRunId ?? readLastRunId());
  }, [pathRunId]);

  useEffect(() => {
    api
      .settings()
      .then((data) => {
        const value = data.langsmith as { connected: boolean; project: string; region: string };
        setLangsmith(value);
      })
      .catch(() => setLangsmith(null));
    api
      .overview()
      .then((data) => {
        setIdentityLabel(data.identity.label);
        setIdentityRole(data.identity.role);
        if (!readLastRunId() && data.active?.id) rememberRunId(data.active.id);
        setStoredRunId(parseRunId(window.location.pathname) ?? readLastRunId() ?? data.active?.id ?? null);
      })
      .catch(() => undefined);
  }, []);

  const runId = pathRunId ?? storedRunId;

  const researchItems = useMemo(
    () =>
      RESEARCH.map((item) => ({
        ...item,
        label: t(`nav.${item.id}`),
        href: runId ? hrefFor(item.id, runId) : "/research/select",
        enabled: Boolean(runId),
        current: isCurrent(item.id, pathname, runId),
      })),
    [pathname, runId, t],
  );

  return (
    <div className="shell">
      <a className="skip-link" href="#content">
        {t("nav.skip")}
      </a>
      <aside className="sidebar" aria-label={t("nav.primary")}>
        <Link href="/" className="brand">
          <span className="brand-mark">S</span>
          {t("brand.name")}
        </Link>
        <nav className="nav">
          <Link href="/" className={`nav-link ${pathname === "/" ? "active" : ""}`} aria-current={pathname === "/" ? "page" : undefined}>
            <IconHome />
            {t("nav.overview")}
          </Link>
          <Link
            href="/research/new"
            className={`nav-link ${pathname === "/research/new" ? "active" : ""}`}
            aria-current={pathname === "/research/new" ? "page" : undefined}
          >
            <IconPlus />
            {t("nav.newResearch")}
          </Link>
          <div className="nav-section">{t("nav.section.research")}</div>
          {researchItems.map((item) =>
            item.enabled ? (
              <Link key={item.id} href={item.href} className={`nav-link ${item.current ? "active" : ""}`} aria-current={item.current ? "page" : undefined}>
                <item.icon />
                {item.label}
                {item.id === "live" ? <span className="nav-dot" /> : null}
              </Link>
            ) : (
              <button
                key={item.id}
                type="button"
                className="nav-link is-disabled"
                title={t("nav.needsRun")}
                aria-disabled="true"
                onClick={() => router.push("/research/select")}
              >
                <item.icon />
                {item.label}
              </button>
            ),
          )}
          <Link href="/history" className={`nav-link ${pathname === "/history" ? "active" : ""}`}>
            <IconHistory />
            {t("nav.history")}
          </Link>
          <Link href="/knowledge" className={`nav-link ${pathname.startsWith("/knowledge") ? "active" : ""}`}>
            <IconClaims />
            {t("nav.knowledge")}
          </Link>
          <Link href="/monitors" className={`nav-link ${pathname.startsWith("/monitors") ? "active" : ""}`}>
            <IconLive />
            {t("nav.monitors")}
          </Link>
          <Link href="/compare" className={`nav-link ${pathname.startsWith("/compare") ? "active" : ""}`}>
            <IconEvals />
            {t("nav.compare")}
          </Link>
          {runId ? (
            <Link href={`/resume/${runId}`} className={`nav-link ${pathname.startsWith("/resume") ? "active" : ""}`}>
              <IconResume />
              {t("nav.resume")}
            </Link>
          ) : (
            <button type="button" className="nav-link is-disabled" title={t("nav.needsRun")} aria-disabled="true" onClick={() => router.push("/research/select")}>
              <IconResume />
              {t("nav.resume")}
            </button>
          )}
          <Link href="/reviews" className={`nav-link ${pathname === "/reviews" ? "active" : ""}`}>
            <IconEvals />
            {t("nav.reviews")}
          </Link>
          <Link href="/settings" className={`nav-link ${pathname === "/settings" ? "active" : ""}`}>
            <IconSettings />
            {t("nav.settings")}
          </Link>
        </nav>
        <div className="sidebar-foot">
          <div className="status-card">
            <div className="row">
              <span className={`dot ${langsmith?.connected ? "ok" : "muted"}`} />
              LangSmith · {langsmith?.connected ? t("langsmith.connected") : t("langsmith.notConfigured")}
            </div>
            <div className="muted" style={{ marginTop: 6 }}>
              {langsmith?.project ?? "deepscout-dev"} ({langsmith?.region ?? "EU"})
            </div>
          </div>
          <div className="identity-card">
            <span className="identity-avatar" aria-hidden="true">
              {initials(identityLabel)}
            </span>
            <div className="identity-meta">
              <strong>{identityLabel}</strong>
              <div className="muted">{identityRole}</div>
            </div>
          </div>
          <div className="version-tag">v0.1.0</div>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <Link href={runId ? `/research/${runId}` : "/"} className="back-link">
            ← {t("nav.back")}
          </Link>
          <div className="row" aria-label={t("uiLanguage.label")}>
            <div className="lang-switch">
              <button type="button" className={locale === "en" ? "active" : ""} data-testid="ui-lang-en" aria-label="English" onClick={() => setLocale("en")}>
                EN
              </button>
              <button type="button" className={locale === "it" ? "active" : ""} data-testid="ui-lang-it" aria-label="Italiano" onClick={() => setLocale("it")}>
                IT
              </button>
            </div>
          </div>
        </header>
        <div id="content" className="content">
          {children}
        </div>
        <nav className="mobile-nav" aria-label="Mobile">
          <Link href="/">{t("nav.overview")}</Link>
          <Link href="/research/new">{t("nav.mobile.new")}</Link>
          <Link href={runId ? `/research/${runId}` : "/research/select"}>{t("nav.mobile.run")}</Link>
          <Link href="/history">{t("nav.history")}</Link>
          <Link href="/knowledge">{t("nav.knowledge")}</Link>
          <Link href="/settings">{t("nav.settings")}</Link>
        </nav>
      </div>
    </div>
  );
}
