"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, apiUrl } from "@/lib/api";
import { useT } from "@/i18n/context";

const REPO = "https://github.com/francescoveryra-dot/deepscout";

const FEATURES = [
  "landing.feature.planner",
  "landing.feature.workers",
  "landing.feature.evidence",
  "landing.feature.rag",
  "landing.feature.monitor",
  "landing.feature.hitl",
] as const;

export function LandingScreen() {
  const router = useRouter();
  const t = useT();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api
      .me()
      .then((data) => {
        if (data.authenticated) {
          router.replace("/dashboard");
          return;
        }
        setChecking(false);
      })
      .catch(() => setChecking(false));
  }, [router]);

  if (checking) {
    return <p className="muted">{t("landing.loading")}</p>;
  }

  return (
    <div className="landing grid" style={{ gap: 32 }}>
      <section className="landing-hero">
        <p className="card-eyebrow">{t("landing.eyebrow")}</p>
        <h1 className="landing-title">{t("brand.name")}</h1>
        <p className="landing-lead">{t("landing.lead")}</p>
        <div className="row" style={{ flexWrap: "wrap", gap: 10, marginTop: 20 }}>
          <Link href="/demo" className="btn primary" data-testid="landing-demo">
            {t("landing.cta.demo")}
          </Link>
          <a className="btn" href={`${apiUrl}/api/v1/auth/login/github?next=/onboarding`}>
            {t("landing.cta.github")}
          </a>
          <a className="btn" href={`${apiUrl}/api/v1/auth/login/google?next=/onboarding`}>
            {t("landing.cta.google")}
          </a>
        </div>
      </section>

      <section className="card">
        <h2>{t("landing.featuresTitle")}</h2>
        <ul className="landing-features">
          {FEATURES.map((key) => (
            <li key={key}>{t(key)}</li>
          ))}
        </ul>
      </section>

      <section className="grid cols-2">
        <div className="card">
          <h2>{t("landing.tryTitle")}</h2>
          <p className="muted">{t("landing.tryBody")}</p>
          <Link href="/demo" className="btn" style={{ marginTop: 12 }}>
            {t("landing.cta.demo")}
          </Link>
        </div>
        <div className="card">
          <h2>{t("landing.ossTitle")}</h2>
          <div className="row" style={{ flexWrap: "wrap", gap: 8, marginTop: 12 }}>
            <a className="btn" href={REPO}>
              {t("landing.link.github")}
            </a>
            <a className="btn" href={`${REPO}#quick-start`}>
              {t("landing.link.local")}
            </a>
            <a className="btn" href={`${REPO}/blob/main/docs/DEPLOYMENT.md`}>
              {t("landing.link.deploy")}
            </a>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>{t("landing.learnTitle")}</h2>
        <div className="row" style={{ flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          <a className="btn ghost" href={`${REPO}/blob/main/ARCHITECTURE.md`}>
            {t("landing.link.architecture")}
          </a>
          <a className="btn ghost" href={`${REPO}/blob/main/SECURITY.md`}>
            {t("landing.link.security")}
          </a>
          <a className="btn ghost" href={`${REPO}/blob/main/README.md`}>
            {t("landing.link.docs")}
          </a>
        </div>
      </section>
    </div>
  );
}
