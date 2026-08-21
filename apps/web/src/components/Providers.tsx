"use client";

import type { ReactNode } from "react";
import { I18nProvider } from "@/i18n/context";
import { RumCollector } from "@/lib/rum";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <RumCollector />
      {children}
    </I18nProvider>
  );
}
