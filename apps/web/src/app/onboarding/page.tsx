"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";

export default function OnboardingPage() {
  const t = useT();
  const [name, setName] = useState("");

  useEffect(() => {
    api.me().then((data) => {
      if (data.display_name) setName(data.display_name);
    }).catch(() => undefined);
  }, []);

  return (
    <div className="grid" style={{ gap: 18, maxWidth: 640 }}>
      <h1 className="page-title">{t("onboarding.welcome", { name: name || t("onboarding.fallbackName") })}</h1>
      <ol className="list">
        <li>{t("onboarding.stepProviders")}</li>
        <li>{t("onboarding.stepReadiness")}</li>
        <li>{t("onboarding.stepResearch")}</li>
      </ol>
      <p>{t("onboarding.langsmith")}</p>
      <div className="chip-row">
        <Link className="btn primary" href="/account">
          {t("new.configureProviders")}
        </Link>
        <Link className="btn" href="/research/new">
          {t("action.start")}
        </Link>
      </div>
    </div>
  );
}
