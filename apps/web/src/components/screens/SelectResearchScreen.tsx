"use client";

import Link from "next/link";
import { useT } from "@/i18n/context";

export function SelectResearchScreen() {
  const t = useT();
  return (
    <div className="card">
      <h1 className="page-title">{t("select.title")}</h1>
      <p className="page-sub">{t("select.body")}</p>
      <div className="row" style={{ marginTop: 16 }}>
        <Link className="btn primary" href="/research/new">
          {t("nav.newResearch")}
        </Link>
        <Link className="btn" href="/history">
          {t("nav.history")}
        </Link>
      </div>
    </div>
  );
}
