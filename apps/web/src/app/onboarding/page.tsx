"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function OnboardingPage() {
  const [name, setName] = useState("there");

  useEffect(() => {
    api.me().then((data) => {
      if (data.display_name) setName(data.display_name);
    }).catch(() => undefined);
  }, []);

  return (
    <div className="grid" style={{ gap: 18, maxWidth: 640 }}>
      <h1 className="page-title">Welcome, {name}</h1>
      <ol className="list">
        <li>Configure required providers (LLM + search).</li>
        <li>Validate readiness on the account page.</li>
        <li>Start your first research run.</li>
      </ol>
      <p>LangSmith is optional and off unless you supply your own key.</p>
      <div className="chip-row">
        <Link className="btn primary" href="/account">
          Configure providers
        </Link>
        <Link className="btn" href="/research/new">
          Start research
        </Link>
      </div>
    </div>
  );
}
