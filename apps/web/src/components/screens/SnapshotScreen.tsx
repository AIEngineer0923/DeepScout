"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { ExternalLink } from "@/components/ExternalLink";
import { StatusBadge } from "@/components/StatusBadge";

export function SnapshotScreen({ snapshotId }: { snapshotId: string }) {
  const { workspace } = useRun();
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [highlight, setHighlight] = useState(true);
  useEffect(() => {
    if (!workspace) return;
    api.snapshot(workspace.run_id, snapshotId).then(setDetail).catch(() => setDetail(null));
  }, [workspace, snapshotId]);
  const snapshot = detail?.snapshot as { content_text?: string; url?: string; mime_type?: string; byte_size?: number; content_hash?: string; retrieved_at?: string; source_title?: string } | undefined;
  const evidence = (detail?.evidence as Array<{ id: string; quote: string; claim_id: string }>) ?? [];
  const text = snapshot?.content_text ?? "";
  const highlighted = useMemo(() => {
    if (!highlight || !text) return [{ text, id: null }];
    const parts: Array<{ text: string; id: string | null }> = [];
    let remaining = text;
    evidence.forEach((item) => {
      const idx = remaining.toLowerCase().indexOf(item.quote.slice(0, 80).toLowerCase());
      if (idx < 0) return;
      parts.push({ text: remaining.slice(0, idx), id: null });
      parts.push({ text: remaining.slice(idx, idx + item.quote.length), id: item.id });
      remaining = remaining.slice(idx + item.quote.length);
    });
    parts.push({ text: remaining, id: null });
    return parts.length ? parts : [{ text, id: null }];
  }, [text, evidence, highlight]);
  if (!workspace) return <p className="empty">Loading snapshot…</p>;
  return (
    <div>
      <RunHeader workspace={workspace} />
      <div className="grid cols-2">
        <section className="card">
          <h2 className="wrap-text">{snapshot?.source_title ?? "Source snapshot"}</h2>
          {snapshot?.url ? <p><ExternalLink href={snapshot.url}>{snapshot.url}</ExternalLink></p> : null}
          <div className="grid cols-metrics">
            <article className="metric"><div className="k">Fetched</div><div className="v" style={{ fontSize: 13 }}>{snapshot?.retrieved_at ?? "—"}</div></article>
            <article className="metric"><div className="k">Type</div><div className="v" style={{ fontSize: 13 }}>{snapshot?.mime_type ?? "—"}</div></article>
            <article className="metric"><div className="k">Size</div><div className="v" style={{ fontSize: 13 }}>{snapshot?.byte_size ?? "—"}</div></article>
            <article className="metric"><div className="k">Hash</div><div className="v mono" style={{ fontSize: 12 }}>{snapshot?.content_hash?.slice(0, 12) ?? "—"}</div></article>
          </div>
          <div className="toolbar">
            <label className="row"><input type="checkbox" checked={highlight} onChange={(e) => setHighlight(e.target.checked)} /> Highlight evidence</label>
            {snapshot ? <a className="btn" href={api.exportUrl(workspace.run_id, "snapshot-text", snapshotId)}>Download text</a> : null}
          </div>
          <pre className="wrap-text" style={{ maxHeight: 480, overflow: "auto", background: "#f8fafc", padding: 12, borderRadius: 8 }}>
            {highlighted.map((part, index) => (
              <span key={index} id={part.id ?? undefined} style={part.id ? { background: "#fef08a" } : undefined}>{part.text}</span>
            ))}
          </pre>
        </section>
        <aside className="drawer">
          <h2>Evidence from this snapshot</h2>
          {evidence.map((item) => (
            <article key={item.id} style={{ marginBottom: 12 }}>
              <Link href={`/research/${workspace.run_id}/claims?claim=${item.claim_id}`}>{item.id.slice(0, 8)}</Link>
              <p className="wrap-text muted">“{item.quote}”</p>
            </article>
          ))}
          {!evidence.length ? <p className="empty">No evidence linked yet.</p> : null}
          <Link href={`/research/${workspace.run_id}/claims`}>View in evidence tab</Link>
        </aside>
      </div>
    </div>
  );
}
