"use client";
import { Suspense } from "react";
import { CompareScreen } from "@/components/screens/CompareScreen";
import { useT } from "@/i18n/context";
export default function Page() {
  const t = useT();
  return (
    <Suspense fallback={<p className="empty">{t("landing.loading")}</p>}>
      <CompareScreen />
    </Suspense>
  );
}
