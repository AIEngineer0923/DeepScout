"use client";

import Link from "next/link";
import { useRun } from "@/components/run/RunProvider";
import { RunHeader } from "@/components/run/RunHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { useT, useI18n } from "@/i18n/context";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";
import { ExpandableText } from "@/components/ExpandableText";
import { AutoLinkText } from "@/components/AutoLinkText";
import { presentSnapshotSummary } from "@/presentation/fields";

export function SnapshotsScreen() {
  const { workspace } = useRun();
  const t = useT();
  const { locale } = useI18n();
  const demoReadOnly = useDemoReadOnly();
  if (!workspace) return <p className="empty">{t("live.loading")}</p>;
  return (
    <div>
      <RunHeader workspace={workspace} />
      {demoReadOnly ? <p className="screen-intro">{t("demo.snapshot.intro")}</p> : null}
      <section className="card">
        <h2>{t("snapshot.listTitle")}</h2>
        {workspace.snapshots.length === 0 ? <p className="empty">{t("snapshot.empty")}</p> : null}
        {workspace.snapshots.map((item) => (
          <article key={item.id} className="card snapshot-card compact">
            <ExpandableText text={item.source_title} />
            <p className="muted snapshot-url">
              <AutoLinkText text={item.url} />
            </p>
            <p className="muted">{presentSnapshotSummary(item, locale)}</p>
            <div className="row snapshot-actions">
              <Link className="btn" href={`/research/${workspace.run_id}/snapshots/${item.id}`}>
                {t("snapshot.viewContent")}
              </Link>
              <a className="btn" href={api.exportUrl(workspace.run_id, "snapshot-text", item.id)}>
                {t("snapshot.download")}
              </a>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
