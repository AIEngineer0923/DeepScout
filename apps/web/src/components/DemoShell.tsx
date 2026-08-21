"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useI18n } from "@/i18n/context";
import { parseRunIdFromPath } from "@/lib/routing";

const DEMO_TABS = [
  { id: "live", suffix: "" },
  { id: "plan", suffix: "/plan" },
  { id: "workers", suffix: "/workers" },
  { id: "sources", suffix: "/sources" },
  { id: "snapshot", suffix: "/snapshots" },
  { id: "claims", suffix: "/claims" },
  { id: "quality", suffix: "/quality" },
  { id: "report", suffix: "/report" },
  { id: "evaluations", suffix: "/evaluations" },
] as const;

export function DemoShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { t, locale, setLocale } = useI18n();
  const runId = parseRunIdFromPath(pathname);

  return (
    <div className="public-shell" data-testid="demo-shell">
      <header className="public-header">
        <Link href="/demo" className="brand">
          <span className="brand-mark">S</span>
          {t("brand.name")}
        </Link>
        <span className="badge run">{t("demo.title")}</span>
        <div className="row" style={{ marginLeft: "auto" }} aria-label={t("uiLanguage.label")}>
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
      {runId ? (
        <nav className="demo-run-nav" aria-label={t("nav.section.research")}>
          {DEMO_TABS.map((tab) => {
            const href = `/research/${runId}${tab.suffix}`;
            const active = tab.suffix === "" ? pathname === href : pathname.startsWith(href);
            return (
              <Link key={tab.id} href={href} className={active ? "active" : ""}>
                {t(`nav.${tab.id}`)}
              </Link>
            );
          })}
        </nav>
      ) : null}
      <main className="public-main" id="content">
        {children}
      </main>
      <footer className="public-footer">
        <p className="muted" style={{ margin: 0 }}>
          {t("demo.readOnlyFooter")}
        </p>
      </footer>
    </div>
  );
}
