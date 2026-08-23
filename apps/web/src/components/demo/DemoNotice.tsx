"use client";

import type { ReactNode } from "react";
import { useT } from "@/i18n/context";

/** Explains the read-only demo, and carries the sign-in call to action with it. */
export function DemoNotice({ action }: { action?: ReactNode }) {
  const t = useT();
  return (
    <aside className="demo-notice" data-testid="demo-notice">
      <div className="demo-notice-copy">
        <p className="demo-notice-title">{t("demo.notice.title")}</p>
        <p className="demo-notice-body">{t("demo.notice.body")}</p>
      </div>
      {action ? <div className="demo-notice-action">{action}</div> : null}
    </aside>
  );
}
