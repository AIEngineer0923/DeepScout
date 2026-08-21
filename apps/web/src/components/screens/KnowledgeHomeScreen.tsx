"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";

export function KnowledgeHomeScreen() {
  const t = useT();
  const [runs, setRuns] = useState<Array<{ run_id: string; goal: string; page_count: number }>>([]);
  useEffect(() => {
    api.knowledgeRuns().then(setRuns).catch(() => setRuns([]));
  }, []);
  return (
    <div>
      <h1 className="page-title">{t("knowledge.title")}</h1>
      <p className="page-sub">{t("knowledge.subtitle")}</p>
      <p className="muted">{t("knowledge.notEvidence")}</p>
      <div className="card">
        {runs.length === 0 ? <p className="empty">{t("knowledge.empty")}</p> : null}
        <ul>
          {runs.map((run) => (
            <li key={run.run_id}>
              <Link href={`/knowledge/${run.run_id}`}>{run.goal}</Link>
              <span className="muted"> · {run.page_count} {t("knowledge.pages")}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
