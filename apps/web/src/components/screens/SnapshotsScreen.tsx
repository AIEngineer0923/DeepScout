"use client";

import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";
import { ExpandableText } from "@/components/ExpandableText";

export function SnapshotsScreen() {
  const { workspace } = useRun();
  const t = useT();
  if (!workspace) return <p className="empty">{t("live.loading")}</p>;
  return (
    <div>
      <RunHeader workspace={workspace} />
      <section className="card">
        <h2>{t("snapshot.listTitle")}</h2>
        {workspace.snapshots.length === 0 ? <p className="empty">{t("snapshot.empty")}</p> : null}
        {workspace.snapshots.map((item) => (
          <article key={item.id} className="card" style={{ marginBottom: 12 }}>
            <ExpandableText text={item.source_title} />
            <p className="muted wrap-text">{item.url}</p>
            <p className="muted">
              {item.mime_type} · {item.word_count} · {item.evidence_count}
            </p>
            <Link className="btn" href={`/research/${workspace.run_id}/snapshots/${item.id}`}>
              {t("action.view")}
            </Link>
            <a className="btn" href={api.exportUrl(workspace.run_id, "snapshot-text", item.id)}>
              {t("snapshot.download")}
            </a>
          </article>
        ))}
      </section>
    </div>
  );
}
