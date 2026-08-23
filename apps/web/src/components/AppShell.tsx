"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import { IconMenu } from "@/components/Icons";
import { AccountMenu } from "@/components/navigation/AccountMenu";
import { AppNavPanel } from "@/components/navigation/AppNavPanel";
import { MobileDrawer } from "@/components/navigation/MobileDrawer";
import { useAppNavigation } from "@/components/navigation/useAppNavigation";
import { api } from "@/lib/api";
import { parseRunId, readLastRunId, rememberRunId, clearLastRunId } from "@/lib/current-run";
import { useI18n } from "@/i18n/context";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { t, locale, setLocale } = useI18n();
  const demoReadOnly = useDemoReadOnly();
  const pathRunId = parseRunId(pathname);
  const [storedRunId, setStoredRunId] = useState<string | null>(null);
  const [langsmith, setLangsmith] = useState<{ connected: boolean; project: string; region: string } | null>(null);
  const [identityLabel, setIdentityLabel] = useState("");
  const [identityRole, setIdentityRole] = useState("Operator");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isHosted, setIsHosted] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

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

  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  const runId = pathRunId ?? storedRunId;
  const overviewHref = demoReadOnly ? "/demo" : "/dashboard";
  const newResearchHref = demoReadOnly ? "/login?next=/research/new" : "/research/new";
  const displayIdentityLabel = demoReadOnly ? t("demo.visitor") : identityLabel || t("identity.label");
  const displayIdentityRole = demoReadOnly
    ? t("demo.publicBadge")
    : identityRole === "Anonymous"
      ? t("identity.anonymous")
      : identityRole === "Authenticated"
        ? t("identity.authenticated")
        : t("identity.operator");

  const navItems = useAppNavigation({
    demoReadOnly,
    runId,
    isAuthenticated,
    isHosted,
    overviewHref,
    newResearchHref,
  });

  return (
    <div className="shell" data-testid={demoReadOnly ? "demo-shell" : "app-shell"}>
      <a className="skip-link" href="#content">
        {t("nav.skip")}
      </a>
      <aside className="sidebar desktop-only" aria-label={t("nav.primary")}>
        <Link href={overviewHref} className="brand">
          <span className="brand-mark">S</span>
          {t("brand.name")}
        </Link>
        {demoReadOnly ? <span className="demo-badge sidebar-demo-badge">{t("demo.badge")}</span> : null}
        <AppNavPanel items={navItems} />
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
          <AccountMenu
            label={displayIdentityLabel}
            role={displayIdentityRole}
            demoReadOnly={demoReadOnly}
            isAuthenticated={isAuthenticated}
            isHosted={isHosted}
          />
          <div className="version-tag">v0.1.0</div>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <div className="topbar-start">
            <button
              type="button"
              className="icon-btn mobile-menu-btn"
              aria-label={t("nav.menu")}
              aria-expanded={drawerOpen}
              data-testid="mobile-menu-button"
              onClick={() => setDrawerOpen(true)}
            >
              <IconMenu />
            </button>
            <Link href={runId ? `/research/${runId}` : overviewHref} className="back-link topbar-back">
              ← {demoReadOnly ? t("demo.backToCatalog") : t("nav.back")}
            </Link>
            <Link href={overviewHref} className="brand mobile-brand">
              <span className="brand-mark">S</span>
              {t("brand.name")}
            </Link>
          </div>
          <div className="topbar-end" aria-label={t("uiLanguage.label")}>
            {demoReadOnly ? <span className="demo-readonly-pill topbar-demo-pill">{t("demo.readOnlyPill")}</span> : null}
            <div className="lang-switch">
              <button
                type="button"
                className={locale === "en" ? "active" : ""}
                data-testid="ui-lang-en"
                aria-label="English"
                onClick={() => setLocale("en")}
              >
                EN
              </button>
              <button
                type="button"
                className={locale === "it" ? "active" : ""}
                data-testid="ui-lang-it"
                aria-label="Italiano"
                onClick={() => setLocale("it")}
              >
                IT
              </button>
            </div>
          </div>
        </header>
        <div id="content" className="content">
          <div className="content-inner">{children}</div>
        </div>
      </div>
      <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        {demoReadOnly ? <span className="demo-badge drawer-demo-badge">{t("demo.badge")}</span> : null}
        <AppNavPanel items={navItems} onNavigate={() => setDrawerOpen(false)} />
        <div className="mobile-drawer-foot">
          <AccountMenu
            label={displayIdentityLabel}
            role={displayIdentityRole}
            demoReadOnly={demoReadOnly}
            isAuthenticated={isAuthenticated}
            isHosted={isHosted}
          />
        </div>
      </MobileDrawer>
    </div>
  );
}
