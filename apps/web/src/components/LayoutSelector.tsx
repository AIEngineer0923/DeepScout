"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import { DemoShell } from "@/components/DemoShell";
import { HostedAppGate } from "@/components/HostedAppGate";
import { PublicShell } from "@/components/PublicShell";
import { api } from "@/lib/api";
import { isDemoRunPath, isPublicEntryPath } from "@/lib/routing";

type ShellKind = "public" | "demo" | "app" | "loading";

export function LayoutSelector({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [shell, setShell] = useState<ShellKind>("loading");

  useEffect(() => {
    if (isPublicEntryPath(pathname)) {
      setShell("public");
      return;
    }

    api
      .me()
      .then((me) => {
        const hosted = me.mode === "hosted";
        const authenticated = Boolean(me.authenticated);

        if (!hosted || authenticated) {
          setShell("app");
          return;
        }

        if (isDemoRunPath(pathname)) {
          setShell("demo");
          return;
        }

        setShell("app");
      })
      .catch(() => setShell("app"));
  }, [pathname]);

  if (shell === "loading") {
    return (
      <div className="public-main" data-testid="layout-loading">
        <p className="muted">…</p>
      </div>
    );
  }

  if (shell === "public") {
    return <PublicShell>{children}</PublicShell>;
  }

  if (shell === "demo") {
    return (
      <HostedAppGate>
        <DemoShell>{children}</DemoShell>
      </HostedAppGate>
    );
  }

  return (
    <HostedAppGate>
      <AppShell>{children}</AppShell>
    </HostedAppGate>
  );
}
