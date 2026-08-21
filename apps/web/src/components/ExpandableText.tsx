"use client";

import { useState } from "react";
import { useT } from "@/i18n/context";

export function ExpandableText({
  text,
  lines = 3,
  className = "",
}: {
  text: string;
  lines?: number;
  className?: string;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const long = text.length > 140 || text.split("\n").length > lines;
  return (
    <div className={className}>
      <p className={`wrap-text ${open || !long ? "" : "clamp-text"}`}>{text}</p>
      {long ? (
        <button type="button" className="link-btn" onClick={() => setOpen((value) => !value)}>
          {open ? t("expand.hide") : t("expand.show")}
        </button>
      ) : null}
    </div>
  );
}
