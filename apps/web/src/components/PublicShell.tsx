"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useI18n } from "@/i18n/context";

const REPO = "https://github.com/francescoveryra-dot/deepscout";

export function PublicShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { t, locale, setLocale } = useI18n();

  return (
    <div className="public-shell" data-testid="public-shell">
      <header className="public-header">
        <Link href="/" className="brand public-brand">
          <span className="brand-mark">S</span>
          {t("brand.name")}
        </Link>
        <div className="public-header-actions">
          <div className="lang-switch" aria-label={t("uiLanguage.label")}>
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
          <Link href="/login" className="btn primary">
            {t("landing.cta.signIn")}
          </Link>
        </div>
        <nav className="public-nav" aria-label={t("landing.nav")}>
          <Link href="/demo" className={pathname === "/demo" ? "active" : ""}>
            {t("landing.cta.demo")}
          </Link>
          <a href={`${REPO}/blob/main/ARCHITECTURE.md`}>{t("landing.link.architecture")}</a>
          <a href={`${REPO}/blob/main/SECURITY.md`}>{t("landing.link.security")}</a>
          <a href={`${REPO}/blob/main/docs/DEPLOYMENT.md`}>{t("landing.link.deploy")}</a>
        </nav>
      </header>
      <main className="public-main">{children}</main>
      <footer className="public-footer">
        <nav className="public-footer-links" aria-label={t("landing.footerNav")}>
          <a href={REPO}>{t("landing.link.github")}</a>
          <a href={`${REPO}#quick-start`}>{t("landing.link.local")}</a>
          <a href={`${REPO}/blob/main/docs/DEPLOYMENT.md`}>{t("landing.link.deploy")}</a>
          <a href={`${REPO}/blob/main/README.md`}>{t("landing.link.docs")}</a>
        </nav>
        <p className="public-footer-note">{t("landing.footer")}</p>
      </footer>
    </div>
  );
}
