"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import { PublicShell } from "@/components/PublicShell";

const PUBLIC_EXACT = new Set(["/", "/demo", "/login"]);

export function LayoutSelector({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (PUBLIC_EXACT.has(pathname)) {
    return <PublicShell>{children}</PublicShell>;
  }
  return <AppShell>{children}</AppShell>;
}
