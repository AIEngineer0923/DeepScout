"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Overview } from "@/lib/types";
import { useT } from "@/i18n/context";

export default function DemoPage() {
  const t = useT();
  const [overview, setOverview] = useState<Overview | null>(null);

  useEffect(() => {
    api.overview().then(setOverview).catch(() => setOverview(null));
  }, []);

  const items = overview?.recent ?? [];

  return (
    <div className="grid" style={{ gap: 22 }}>
      <div className="page-head">
        <h1 className="page-title">{t("demo.title")}</h1>
        <p className="page-sub">{t("demo.subtitle")}</p>
      </div>
      <section className="card">
        {items.length === 0 ? (
          <p>{t("demo.empty")}</p>
        ) : (
          <ul className="list">
            {items.map((item) => (
              <li key={item.id}>
                <Link href={`/research/${item.id}`}>{item.goal}</Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      <Link href="/login" className="btn primary">
        {t("demo.cta")}
      </Link>
    </div>
  );
}
