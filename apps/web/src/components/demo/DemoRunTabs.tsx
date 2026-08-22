"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useT } from "@/i18n/context";

const TABS = [
  { id: "live", suffix: "" },
  { id: "plan", suffix: "/plan" },
  { id: "workers", suffix: "/workers" },
  { id: "sources", suffix: "/sources" },
  { id: "snapshot", suffix: "/snapshots" },
  { id: "claims", suffix: "/claims" },
  { id: "quality", suffix: "/quality" },
  { id: "report", suffix: "/report" },
  { id: "evaluations", suffix: "/evaluations" },
] as const;

export function DemoRunTabs({ runId }: { runId: string }) {
  const pathname = usePathname();
  const t = useT();
  const base = `/research/${runId}`;

  return (
    <nav className="demo-workspace-nav" aria-label={t("nav.research")} data-testid="demo-run-tabs">
      <div className="demo-workspace-tabs" role="tablist">
        {TABS.map((tab) => {
          const href = `${base}${tab.suffix}`;
          const active = tab.suffix === "" ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={tab.id}
              href={href}
              className={`demo-tab ${active ? "active" : ""}`}
              aria-current={active ? "page" : undefined}
              role="tab"
            >
              {t(`nav.${tab.id}`)}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
