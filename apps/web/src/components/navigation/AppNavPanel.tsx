"use client";

import Link from "next/link";
import type { AppNavItem } from "./useAppNavigation";
import { useT } from "@/i18n/context";

export function AppNavPanel({
  items,
  onNavigate,
}: {
  items: AppNavItem[];
  onNavigate?: () => void;
}) {
  const t = useT();

  return (
    <nav className="nav">
      {items.map((item) => {
        if (item.section === "label") {
          return (
            <div key={item.id} className="nav-section">
              {item.label}
            </div>
          );
        }

        const className = `nav-link ${item.current ? "active" : ""} ${item.enabled ? "" : "is-disabled"}`.trim();
        const content = (
          <>
            {item.icon ? <item.icon /> : null}
            {item.label}
            {item.id === "live" && item.enabled ? <span className="nav-dot" /> : null}
          </>
        );

        if (!item.enabled) {
          return (
            <button
              key={item.id}
              type="button"
              className={className}
              title={t("nav.needsRun")}
              aria-disabled="true"
              onClick={() => {
                item.onDisabledClick?.();
                onNavigate?.();
              }}
            >
              {content}
            </button>
          );
        }

        return (
          <Link
            key={item.id}
            href={item.href}
            className={className}
            aria-current={item.current ? "page" : undefined}
            onClick={onNavigate}
          >
            {content}
          </Link>
        );
      })}
    </nav>
  );
}
