"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, apiUrl } from "@/lib/api";
import { useT } from "@/i18n/context";

function safeNextPath(raw: string | null): string {
  const candidate = (raw || "/onboarding").trim();
  if (!candidate.startsWith("/") || candidate.startsWith("//") || candidate.includes("://")) {
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
    <div className="grid" style={{ gap: 22, maxWidth: 520 }}>
      <div className="page-head">
        <h1 className="page-title">{t("login.title")}</h1>
        <p className="page-sub">{t("login.subtitle")}</p>
      </div>
      <section className="card" style={{ display: "grid", gap: 12 }}>
        {mode === "hosted" && !ready ? (
          <p>{t("login.notReady")}</p>
        ) : (
          <>
            <a className="btn primary" href={`${apiUrl}/api/v1/auth/login/github?next=${encodeURIComponent(nextPath)}`}>
              {t("login.github")}
            </a>
            <a className="btn" href={`${apiUrl}/api/v1/auth/login/google?next=${encodeURIComponent(nextPath)}`}>
              {t("login.google")}
            </a>
          </>
        )}
        <Link href="/demo" className="btn">
          {t("login.demo")}
        </Link>
      </section>
    </div>
  );
}
