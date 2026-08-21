"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";

type Page = { id: string; title: string; slug: string; status: string; page_type: string };

export function KnowledgeRunScreen() {
  const t = useT();
  const params = useParams<{ runId: string }>();
  const runId = params.runId;
  const [pages, setPages] = useState<Page[]>([]);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Array<{ id: string; text: string }>>([]);
  const [graph, setGraph] = useState<{ nodes: Array<{ id: string; label: string }>; edges: Array<{ from: string; to: string; type: string }> } | null>(null);
  useEffect(() => {
    api.knowledgePages(runId).then((rows) => setPages(rows as Page[])).catch(() => setPages([]));
    api.knowledgeGraph(runId).then((data) => setGraph(data as never)).catch(() => setGraph(null));
  }, [runId]);
  async function search() {
    if (!q.trim()) return;
    const data = await api.knowledgeSearch(runId, q.trim());
    const items = (data.items as Array<{ id: string; text: string }>) ?? [];
    setHits(items);
  }
  return (
    <div>
      <h1 className="page-title">{t("knowledge.runTitle")}</h1>
      <p className="muted">{t("knowledge.notEvidence")}</p>
      <div className="toolbar">
        <input className="input grow" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("knowledge.search")} />
        <button className="btn" type="button" onClick={() => void search()}>{t("action.search")}</button>
        <Link href={`/research/${runId}`}>{t("knowledge.openRun")}</Link>
      </div>
      {hits.length ? (
        <section className="card">
          <h2>{t("knowledge.compiledHits")}</h2>
          <ul>
            {hits.map((hit) => (
              <li key={hit.id}>
                <Link href={`/knowledge/${runId}/statement/${hit.id}`}>{hit.text}</Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <div className="grid cols-2">
        <section className="card">
          <h2>{t("knowledge.pages")}</h2>
          <ul>
            {pages.map((page) => (
              <li key={page.id}>
                <Link href={`/knowledge/${runId}/page/${page.id}`}>{page.title}</Link>
                <span className="muted"> · {page.page_type} · {page.status}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="card">
          <h2>{t("knowledge.graph")}</h2>
          <p className="muted">{t("knowledge.graphHelp")}</p>
          {graph?.nodes?.length ? (
            <svg viewBox="0 0 320 220" width="100%" height="220" role="img" aria-label={t("knowledge.graph")}>
              {graph.nodes.slice(0, 12).map((node, index) => {
                const angle = (index / Math.min(graph.nodes.length, 12)) * Math.PI * 2;
                const x = 160 + Math.cos(angle) * 90;
                const y = 110 + Math.sin(angle) * 70;
                return (
                  <g key={node.id}>
                    <circle cx={x} cy={y} r="8" fill="#2563eb" />
                    <text x={x + 10} y={y + 4} fontSize="9">{node.label.slice(0, 24)}</text>
                  </g>
                );
              })}
            </svg>
          ) : (
            <p className="empty">{t("knowledge.noGraph")}</p>
          )}
          <table className="data">
            <thead><tr><th>{t("knowledge.from")}</th><th>{t("knowledge.to")}</th><th>{t("table.method")}</th></tr></thead>
            <tbody>
              {(graph?.edges ?? []).slice(0, 20).map((edge, index) => (
                <tr key={index}>
                  <td className="wrap-text">{edge.from}</td>
                  <td className="wrap-text">{edge.to}</td>
                  <td>{edge.type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
