"use client";

import { useT } from "@/i18n/context";

export function DemoNotice() {
  const t = useT();
  return (
    <aside className="demo-notice" data-testid="demo-notice">
      <p className="demo-notice-title">{t("demo.notice.title")}</p>
      <p className="demo-notice-body">{t("demo.notice.body")}</p>
    </aside>
  );
}
