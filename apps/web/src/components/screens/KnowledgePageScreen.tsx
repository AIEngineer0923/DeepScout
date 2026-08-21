"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";

export function KnowledgePageScreen() {
  const t = useT();
  const params = useParams<{ runId: string; pageId: string }>();
  const [page, setPage] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    api.knowledgePage(params.pageId).then(setPage).catch(() => setPage(null));
  }, [params.pageId]);
  if (!page) return <p className="empty">{t("knowledge.loading")}</p>;
  const statements = (page.statements as Array<{ id: string; text: string; status: string; claim_id?: string }>) ?? [];
  return (
    <div>
      <h1 className="page-title wrap-text">{String(page.title)}</h1>
      <p className="muted">{t("knowledge.notEvidence")} · v{String(page.version)} · {String(page.status)}</p>
      <pre className="wrap-text">{String(page.body_markdown ?? "")}</pre>
      <section className="card">
        <h2>{t("knowledge.statements")}</h2>
        <ul>
          {statements.map((item) => (
            <li key={item.id}>
              <Link href={`/knowledge/${params.runId}/statement/${item.id}`}>{item.text}</Link>
              <span className="muted"> · {item.status}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
