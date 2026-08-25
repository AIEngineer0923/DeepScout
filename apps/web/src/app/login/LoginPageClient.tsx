"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, apiUrl } from "@/lib/api";
import { useT } from "@/i18n/context";

function safeNextPath(raw: string | null): string {
  const candidate = (raw || "/onboarding").trim();
  if (
    !candidate.startsWith("/") ||
    candidate.startsWith("//") ||
    candidate.includes("://") ||
    candidate.includes("\\") ||
    /[\u0000-\u001F\u007F]/.test(candidate)
  ) {
    return "/onboarding";
  }
  return candidate;
}

export function LoginPageClient() {
  const t = useT();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState("local");
  const [ready, setReady] = useState(true);
  const nextPath = safeNextPath(searchParams.get("next"));

  useEffect(() => {
    api
      .me()
      .then((data) => {
        setMode(data.mode);
        setReady(data.hosted_auth_ready);
        if (data.authenticated) {
          window.location.replace(nextPath === "/onboarding" ? "/dashboard" : nextPath);
        }
      })
      .catch(() => undefined);
  }, [nextPath]);

  return (
    <div className="login-layout">
      <div className="login-intro">
        <h1 className="login-title">{t("login.title")}</h1>
        <p className="login-lead">{t("login.subtitle")}</p>
      </div>
      <section className="card login-card">
        <h2 className="login-card-title">{t("login.authHeading")}</h2>
        {mode === "hosted" && !ready ? (
          <p className="muted">{t("login.notReady")}</p>
        ) : (
          <>
            <div className="login-actions">
              <a
                className="btn primary"
                href={`${apiUrl}/api/v1/auth/login/github?next=${encodeURIComponent(nextPath)}`}
              >
                {t("login.github")}
              </a>
              <a
                className="btn"
                href={`${apiUrl}/api/v1/auth/login/google?next=${encodeURIComponent(nextPath)}`}
              >
                {t("login.google")}
              </a>
            </div>
            <p className="login-help">{t("login.authHelp")}</p>
          </>
        )}
      </section>
      <section className="login-secondary">
        <h2 className="login-card-title">{t("login.demoHeading")}</h2>
        <p className="login-help">{t("login.demoHelp")}</p>
        <Link href="/demo" className="btn">
          {t("login.demo")}
        </Link>
      </section>
    </div>
  );
}
