"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { DemoRunTabs } from "@/components/demo/DemoRunTabs";
import { useI18n } from "@/i18n/context";
import { parseRunIdFromPath } from "@/lib/routing";

export function DemoShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { t, locale, setLocale } = useI18n();
  const runId = parseRunIdFromPath(pathname);

  return (
    <div className="public-shell demo-shell" data-testid="demo-shell">
      <header className="demo-app-header">
        <div className="demo-app-header-left">
          <Link href="/demo" className="brand">
            <span className="brand-mark">S</span>
            {t("brand.name")}
          </Link>
          <span className="demo-badge">{t("demo.badge")}</span>
          {runId ? (
            <Link href="/demo" className="demo-back-link">
              {t("demo.backToCatalog")}
            </Link>
          ) : null}
        </div>
        <div className="demo-app-header-right" aria-label={t("uiLanguage.label")}>
          <div className="lang-switch">
            <button
              type="button"
              className={locale === "en" ? "active" : ""}
              aria-label="English"
              onClick={() => setLocale("en")}
            >
              EN
            </button>
            <button
              type="button"
              className={locale === "it" ? "active" : ""}
              aria-label="Italiano"
              onClick={() => setLocale("it")}
            >
              IT
            </button>
          </div>
          <Link href="/login" className="btn primary">
            {t("landing.cta.signIn")}
          </Link>
        </div>
      </header>
      {runId ? <DemoRunTabs runId={runId} /> : null}
      <main className="public-main demo-main" id="content">
        {children}
      </main>
      <footer className="public-footer demo-footer">
        <p className="muted" style={{ margin: 0 }}>
          {t("demo.readOnlyFooter")}
        </p>
      </footer>
    </div>
  );
}
