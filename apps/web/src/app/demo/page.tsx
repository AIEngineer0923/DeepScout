"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DemoCatalogItem } from "@/lib/types";
import { useI18n } from "@/i18n/context";
import { relativeTime } from "@/lib/format";

function categoryLabel(t: (key: string) => string, category?: string | null) {
  if (!category) return t("demo.category.general");
  const key = `demo.category.${category}`;
  const translated = t(key);
  return translated === key ? category : translated;
}

export default function DemoPage() {
  const { t, locale } = useI18n();
  const [items, setItems] = useState<DemoCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .demos(locale)
      .then((data) => setItems(data.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [locale]);

  return (
    <div className="grid" style={{ gap: 22 }}>
      <div className="page-head">
        <h1 className="page-title" style={{ fontSize: "clamp(1.75rem, 4vw, 2.25rem)" }}>
          {t("demo.title")}
        </h1>
        <p className="page-sub">{t("demo.subtitle")}</p>
      </div>
      {loading ? (
        <p className="muted">{t("landing.loading")}</p>
      ) : items.length === 0 ? (
        <section className="card">
          <p>{t("demo.empty")}</p>
        </section>
      ) : (
        <div className="grid cols-2">
          {items.map((item) => (
            <article key={item.id} className="card demo-card" data-testid="demo-card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <span className="chip">{categoryLabel(t, item.demo_category)}</span>
                {item.completed_at ? (
                  <span className="muted" style={{ fontSize: 13 }}>
                    {relativeTime(item.completed_at, locale)}
                  </span>
                ) : null}
              </div>
              <h2>{item.demo_title || item.goal}</h2>
              {item.demo_summary ? <p className="muted">{item.demo_summary}</p> : null}
              {item.demo_why ? <p style={{ fontSize: 14, lineHeight: 1.5 }}>{item.demo_why}</p> : null}
              <div className="chip-row" style={{ marginTop: 12 }}>
                <span className="chip">
                  {item.source_count} {t("demo.catalog.sources")}
                </span>
                <span className="chip">
                  {item.claim_count} {t("demo.catalog.claims")}
                </span>
                <span className="chip">
                  {item.task_count} {t("demo.catalog.tasks")}
                </span>
              </div>
              <Link
                href={`/research/${item.id}`}
                className="btn primary"
                style={{ marginTop: 16 }}
                data-testid="demo-explore"
              >
                {t("demo.exploreResearch")}
              </Link>
            </article>
          ))}
        </div>
      )}
      <Link href="/login" className="btn">
        {t("demo.cta")}
      </Link>
    </div>
  );
}
