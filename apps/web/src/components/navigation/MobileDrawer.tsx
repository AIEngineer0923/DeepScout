"use client";

import { useEffect, useId, useRef } from "react";
import { IconClose } from "@/components/Icons";
import { useT } from "@/i18n/context";

export function MobileDrawer({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const t = useT();
  const titleId = useId();
  const panelRef = useRef<HTMLElement>(null);
  const lastFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    lastFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const panel = panelRef.current;
    const focusable = panel?.querySelector<HTMLElement>(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    focusable?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      const nodes = panel.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
      );
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
      lastFocusRef.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="mobile-drawer-root" data-testid="mobile-drawer">
      <button type="button" className="mobile-drawer-backdrop" aria-label={t("nav.closeMenu")} onClick={onClose} />
      <aside ref={panelRef} className="mobile-drawer-panel" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="mobile-drawer-head">
          <h2 id={titleId} className="mobile-drawer-title">
            {t("nav.menu")}
          </h2>
          <button type="button" className="icon-btn" aria-label={t("nav.closeMenu")} onClick={onClose}>
            <IconClose />
          </button>
        </div>
        <div className="mobile-drawer-body" role="navigation" aria-label={t("nav.primary")}>
          {children}
        </div>
      </aside>
    </div>
  );
}
