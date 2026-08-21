"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, apiUrl } from "@/lib/api";

export default function LoginPage() {
  const [mode, setMode] = useState("local");
  const [ready, setReady] = useState(true);

  useEffect(() => {
    api
      .me()
      .then((data) => {
        setMode(data.mode);
        setReady(data.hosted_auth_ready);
      })
      .catch(() => undefined);
  }, []);

  return (
    <div className="grid" style={{ gap: 22, maxWidth: 520 }}>
      <div className="page-head">
        <h1 className="page-title">Welcome to Deep Scout</h1>
        <p className="page-sub">
          Continue with GitHub or Google to run your own research with your own provider credentials.
        </p>
      </div>
      <section className="card" style={{ display: "grid", gap: 12 }}>
        {mode === "hosted" && !ready ? (
          <p>Hosted authentication is not configured on this deployment.</p>
        ) : (
          <>
            <a className="btn primary" href={`${apiUrl}/api/v1/auth/login/github?next=/onboarding`}>
              Continue with GitHub
            </a>
            <a className="btn" href={`${apiUrl}/api/v1/auth/login/google?next=/onboarding`}>
              Continue with Google
            </a>
          </>
        )}
        <Link href="/demo" className="btn">
          Explore demo without signing in
        </Link>
      </section>
    </div>
  );
}
