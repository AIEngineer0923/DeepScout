"use client";

import { statusTone } from "@/lib/format";
import { useT } from "@/i18n/context";

export function StatusBadge({ status }: { status: string }) {
  const t = useT();
  const key = `status.${status}`;
  const label = t(key);
  return (
    <span className={`badge ${statusTone(status)}`}>
      <span className={`dot ${statusTone(status)}`} />
      {label === key ? status.replaceAll("_", " ") : label}
    </span>
  );
}
