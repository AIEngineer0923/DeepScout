"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { api } from "@/lib/api";
import { clearLastRunId } from "@/lib/current-run";
import { initials } from "@/lib/visual";
import { useT } from "@/i18n/context";

export function AccountMenu({
  label,
  role,
  demoReadOnly,
  isAuthenticated,
  isHosted,
}: {
  label: string;
  role: string;
  demoReadOnly: boolean;
  isAuthenticated: boolean;
  isHosted: boolean;
}) {
  const t = useT();
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const interactive = !demoReadOnly && (isAuthenticated || !isHosted);

  useEffect(() => {
    if (!interactive || !open) return;
    api
      .account()
      .then((data) => {
        const value = typeof data.email === "string" ? data.email : null;
        setEmail(value);
      })
      .catch(() => setEmail(null));
  }, [interactive, open]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  async function logout() {
    setBusy(true);
    try {
      await api.logout();
      clearLastRunId();
      window.sessionStorage.removeItem("deepscout.principal_id");
      window.location.href = "/login";
    } catch {
      setBusy(false);
    }
  }

  if (!interactive) {
    return (
      <div className="identity-card" data-testid="account-identity">
        <span className="identity-avatar" aria-hidden="true">
          {initials(label)}
        </span>
        <div className="identity-meta">
          <strong>{label}</strong>
          <div className="muted">{role}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="account-menu" ref={rootRef} data-testid="account-menu">
      <button
        type="button"
        className="identity-card identity-trigger"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={menuId}
        data-testid="account-menu-trigger"
        onClick={() => setOpen((value) => !value)}
      >
        <span className="identity-avatar" aria-hidden="true">
          {initials(label)}
        </span>
        <div className="identity-meta">
          <strong>{label}</strong>
          <div className="muted">{role}</div>
        </div>
      </button>
      {open ? (
        <div id={menuId} className="account-menu-panel" role="menu" data-testid="account-menu-panel">
          <div className="account-menu-header">
            <strong>{label}</strong>
            {email ? <div className="muted account-menu-email">{email}</div> : null}
          </div>
          <Link href="/account" className="account-menu-item" role="menuitem" onClick={() => setOpen(false)}>
            {t("nav.account")}
          </Link>
          <Link href="/settings" className="account-menu-item" role="menuitem" onClick={() => setOpen(false)}>
            {t("nav.settings")}
          </Link>
          <button type="button" className="account-menu-item danger" role="menuitem" disabled={busy} onClick={() => void logout()}>
            {t("nav.signOut")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
