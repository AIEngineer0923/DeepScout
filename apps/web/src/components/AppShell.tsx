"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import { RESEARCH_NAV, isResearchNavCurrent, researchHref } from "@/components/research/researchNav";
import { api } from "@/lib/api";
import { parseRunId, readLastRunId, rememberRunId, clearLastRunId } from "@/lib/current-run";
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

const RESEARCH = RESEARCH_NAV.map((item, index) => ({
  ...item,
  icon: [IconLive, IconPlan, IconWorkers, IconSources, IconSnapshot, IconClaims, IconQuality, IconReport, IconEvals][index],
}));

function hrefFor(item: (typeof RESEARCH)[number]["id"], runId: string) {
  return researchHref(item, runId);
}

function isCurrent(item: (typeof RESEARCH)[number]["id"], pathname: string, runId: string | null) {
  if (!runId) return false;
  return isResearchNavCurrent(item, pathname, runId);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t, locale, setLocale } = useI18n();
  const demoReadOnly = useDemoReadOnly();
  const pathRunId = parseRunId(pathname);
  const [storedRunId, setStoredRunId] = useState<string | null>(null);
  const [langsmith, setLangsmith] = useState<{ connected: boolean; project: string; region: string } | null>(null);
  const [identityLabel, setIdentityLabel] = useState("Local workspace");
  const [identityRole, setIdentityRole] = useState("Operator");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isHosted, setIsHosted] = useState(false);

  useEffect(() => {
    if (!demoReadOnly) return;
    setIsHosted(true);
    setIsAuthenticated(false);
    setIdentityLabel(t("demo.visitor"));
    setIdentityRole("Visitor");
    setLangsmith(null);
  }, [demoReadOnly, t]);

  useEffect(() => {
    if (demoReadOnly) return;
    api
      .me()
      .then((me) => {
        setIsAuthenticated(Boolean(me.authenticated));
        setIsHosted(me.mode === "hosted");
        const previous = window.sessionStorage.getItem("deepscout.principal_id");
        if (me.id && previous && previous !== me.id) {
          clearLastRunId();
          setStoredRunId(parseRunId(window.location.pathname));
        }
        if (me.id) window.sessionStorage.setItem("deepscout.principal_id", me.id);
        else window.sessionStorage.removeItem("deepscout.principal_id");
      })
      .catch(() => undefined);
  }, [demoReadOnly]);

  useEffect(() => {
    if (demoReadOnly) return;
    api
      .settings()
      .then((data) => {
        const value = data.langsmith as { connected: boolean; project: string; region: string };
        setLangsmith(value);
      })
      .catch(() => setLangsmith(null));
  }, [demoReadOnly]);

  useEffect(() => {
    if (demoReadOnly) return;
    api
      .overview()
      .then((data) => {
        setIdentityLabel(data.identity.label);
        setIdentityRole(data.identity.role);
        setIsHosted(data.identity.mode === "hosted");
        setIsAuthenticated(data.identity.role === "Authenticated" || data.identity.role === "Operator");
        if (!readLastRunId() && data.active?.id) rememberRunId(data.active.id);
        setStoredRunId(parseRunId(window.location.pathname) ?? readLastRunId() ?? data.active?.id ?? null);
      })
      .catch(() => undefined);
  }, [demoReadOnly]);

  const runId = pathRunId ?? storedRunId;
  const overviewHref = demoReadOnly ? "/demo" : "/dashboard";
  const newResearchHref = demoReadOnly ? "/login?next=/research/new" : "/research/new";
  const displayIdentityLabel = demoReadOnly ? t("demo.visitor") : identityLabel;
  const displayIdentityRole = demoReadOnly ? t("demo.publicBadge") : identityRole === "Anonymous"
    ? t("identity.anonymous")
    : identityRole === "Authenticated"
      ? t("identity.authenticated")
      : t("identity.operator");

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
    <div className="shell" data-testid={demoReadOnly ? "demo-shell" : "app-shell"}>
      <a className="skip-link" href="#content">
        {t("nav.skip")}
      </a>
      <aside className="sidebar" aria-label={t("nav.primary")}>
        <Link href={overviewHref} className="brand">
          <span className="brand-mark">S</span>
          {t("brand.name")}
        </Link>
        {demoReadOnly ? <span className="demo-badge sidebar-demo-badge">{t("demo.badge")}</span> : null}
        <nav className="nav">
          <Link
            href={overviewHref}
            className={`nav-link ${pathname === overviewHref ? "active" : ""}`}
            aria-current={pathname === overviewHref ? "page" : undefined}
          >
            <IconHome />
            {demoReadOnly ? t("demo.backToCatalog") : t("nav.overview")}
          </Link>
          <Link
            href={newResearchHref}
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
          {!demoReadOnly ? (
            <>
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
              <Link href="/learning" className={`nav-link ${pathname === "/learning" ? "active" : ""}`}>
                <IconEvals />
                {t("nav.learning")}
              </Link>
              <Link href="/demo" className={`nav-link ${pathname === "/demo" ? "active" : ""}`}>
                <IconEvals />
                {t("nav.demo")}
              </Link>
            </>
          ) : null}
          {!isAuthenticated && isHosted ? (
            <Link href="/login" className={`nav-link ${pathname === "/login" ? "active" : ""}`}>
              <IconSettings />
              {t("nav.signIn")}
            </Link>
          ) : null}
          {!demoReadOnly && (isAuthenticated || !isHosted) ? (
            <Link href="/account" className={`nav-link ${pathname === "/account" ? "active" : ""}`}>
              <IconSettings />
              {t("nav.account")}
            </Link>
          ) : null}
          {!demoReadOnly ? (
            <Link href="/settings" className={`nav-link ${pathname === "/settings" ? "active" : ""}`}>
              <IconSettings />
              {t("nav.settings")}
            </Link>
          ) : null}
        </nav>
        <div className="sidebar-foot">
          {!demoReadOnly ? (
            <div className="status-card">
              <div className="row">
                <span className={`dot ${langsmith?.connected ? "ok" : "muted"}`} />
                LangSmith · {langsmith?.connected ? t("langsmith.connected") : t("langsmith.notConfigured")}
              </div>
              <div className="muted" style={{ marginTop: 6 }}>
                {langsmith?.project ?? "off"} ({langsmith?.region ?? "off"})
              </div>
            </div>
          ) : null}
          <div className="identity-card">
            <span className="identity-avatar" aria-hidden="true">
              {initials(displayIdentityLabel)}
            </span>
            <div className="identity-meta">
              <strong>{displayIdentityLabel}</strong>
              <div className="muted">{displayIdentityRole}</div>
            </div>
          </div>
          <div className="version-tag">v0.1.0</div>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <Link href={runId ? `/research/${runId}` : overviewHref} className="back-link">
            ← {demoReadOnly ? t("demo.backToCatalog") : t("nav.back")}
          </Link>
          <div className="row" aria-label={t("uiLanguage.label")}>
            {demoReadOnly ? <span className="demo-readonly-pill">{t("demo.readOnlyPill")}</span> : null}
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
          <Link href="/dashboard">{t("nav.overview")}</Link>
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
