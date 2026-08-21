"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { isDemoRunPath, isPublicEntryPath } from "@/lib/routing";
import { useT } from "@/i18n/context";

type GateState = "loading" | "allowed" | "redirecting";

export function HostedAppGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const t = useT();
  const [state, setState] = useState<GateState>("loading");

  useEffect(() => {
    if (isPublicEntryPath(pathname)) {
      setState("allowed");
      return;
    }

    api
      .me()
      .then((me) => {
        const hosted = me.mode === "hosted";
        const authenticated = Boolean(me.authenticated);

        if (!hosted || authenticated) {
          setState("allowed");
          return;
        }

        if (isDemoRunPath(pathname)) {
          setState("allowed");
          return;
        }

        setState("redirecting");
        const next = encodeURIComponent(pathname + (searchParams.toString() ? `?${searchParams}` : ""));
        router.replace(`/login?next=${next}`);
      })
      .catch(() => setState("allowed"));
  }, [pathname, router, searchParams]);

  if (state === "loading" || state === "redirecting") {
    return (
      <div className="public-main" data-testid="hosted-auth-gate">
        <p className="muted">{t("landing.loading")}</p>
      </div>
    );
  }

  return <>{children}</>;
}
