"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Overview } from "@/lib/types";

export default function DemoPage() {
  const [overview, setOverview] = useState<Overview | null>(null);

  useEffect(() => {
    api.overview().then(setOverview).catch(() => setOverview(null));
  }, []);

  const items = overview?.recent ?? [];

  return (
    <div className="grid" style={{ gap: 22 }}>
      <div className="page-head">
        <h1 className="page-title">Explore Demo</h1>
        <p className="page-sub">
          Read-only completed research. No signup. No provider spend. Mutation APIs are rejected.
        </p>
      </div>
      <section className="card">
        {items.length === 0 ? (
          <p>No published demo is available on this deployment yet.</p>
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
        Run your own research
      </Link>
    </div>
  );
}
