"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useT } from "@/i18n/context";

export function MonitorDetailScreen() {
  const t = useT();
  const params = useParams<{ monitorId: string }>();
  const router = useRouter();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    api.getMonitor(params.monitorId).then(setData).catch(() => setData(null));
  }, [params.monitorId]);
  if (!data) return <p className="empty">{t("monitors.loading")}</p>;
  const history = (data.history as Array<{ id: string; status: string; created_at: string }>) ?? [];
  return (
    <div>
      <h1 className="page-title">{String(data.name)}</h1>
      <p className="muted wrap-text">{String(data.goal)}</p>
      <p>{t("table.status")}: {String(data.status)} · {String(data.timezone)} · {String(data.schedule_kind)}</p>
      <p>{t("monitors.next")}: {String(data.next_run_at ?? "—")}</p>
      <p>{t("monitors.lastChange")}: {String(data.last_change_at ?? "—")}</p>
      <div className="row">
        <button className="btn" type="button" onClick={() => void api.patchMonitor(params.monitorId, { enabled: !data.enabled }).then(() => location.reload())}>
          {data.enabled ? t("monitors.pause") : t("monitors.enable")}
        </button>
        <button className="btn primary" type="button" onClick={() => void api.runMonitorNow(params.monitorId).then((created) => router.push(`/research/${created.run_id}`))}>
          {t("monitors.runNow")}
        </button>
        <button className="btn" type="button" onClick={() => void api.deleteMonitor(params.monitorId).then(() => router.push("/monitors"))}>
          {t("action.delete")}
        </button>
      </div>
      <section className="card">
        <h2>{t("monitors.history")}</h2>
        <ul>
          {history.map((item, index) => (
            <li key={item.id}>
              <Link href={`/research/${item.id}`}>{item.id}</Link> · {item.status}
              {index > 0 ? (
                <>
                  {" · "}
                  <Link href={`/compare?left=${history[index].id}&right=${history[index - 1].id}`}>{t("compare.open")}</Link>
                </>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
