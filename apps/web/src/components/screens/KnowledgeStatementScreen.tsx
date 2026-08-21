"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";

export function KnowledgeStatementScreen() {
  const t = useT();
  const params = useParams<{ runId: string; statementId: string }>();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    api.knowledgeStatement(params.statementId).then(setData).catch(() => setData(null));
  }, [params.statementId]);
  if (!data) return <p className="empty">{t("knowledge.loading")}</p>;
  const claim = data.claim as { id: string; statement: string } | null;
  const provenance = (data.provenance as Array<{
    evidence_id: string;
    quote: string;
    snapshot_id: string;
    source_id: string | null;
    source_url: string | null;
    passage: string;
  }>) ?? [];
  return (
    <div>
      <h1 className="page-title">{t("knowledge.statement")}</h1>
      <p className="muted" data-testid="knowledge-not-evidence">{t("knowledge.notEvidence")}</p>
      <article className="card">
        <p className="wrap-text">{String(data.text)}</p>
        <p>{t("table.status")}: {String(data.status)}</p>
      </article>
      {claim ? (
        <section className="card">
          <h2>{t("nav.claims")}</h2>
          <p className="wrap-text">{claim.statement}</p>
          <Link href={`/research/${params.runId}/claims`}>{t("knowledge.openClaims")}</Link>
        </section>
      ) : null}
      <section className="card" data-testid="knowledge-provenance">
        <h2>{t("knowledge.provenance")}</h2>
        {provenance.map((item) => (
          <article key={item.evidence_id} className="card">
            <p className="wrap-text"><strong>{t("table.evidence")}</strong>: {item.quote}</p>
            <p className="wrap-text"><strong>{t("nav.snapshot")}</strong>: {item.passage}</p>
            {item.source_url ? (
              <p>
                {t("table.source")}: {item.source_url}
                {item.source_id ? (
                  <>
                    {" · "}
                    <Link href={`/research/${params.runId}/sources/${item.source_id}`} data-testid="knowledge-source-link">{t("action.open")}</Link>
                  </>
                ) : null}
              </p>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}
