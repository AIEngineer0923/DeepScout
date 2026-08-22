"use client";

import { useState, type ReactNode } from "react";
import { useT } from "@/i18n/context";

export function ExpandableText({
  text,
  lines = 3,
  className = "",
  renderText,
}: {
  text: string;
  lines?: number;
  className?: string;
  renderText?: (value: string) => ReactNode;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const long = text.length > 140 || text.split("\n").length > lines;
  const content = renderText ? renderText(text) : text;
  return (
    <div className={className}>
      <p className={`wrap-text ${open || !long ? "" : "clamp-text"}`}>{content}</p>
      {long ? (
        <button type="button" className="link-btn" onClick={() => setOpen((value) => !value)}>
          {open ? t("expand.hide") : t("expand.show")}
        </button>
      ) : null}
    </div>
  );
}
