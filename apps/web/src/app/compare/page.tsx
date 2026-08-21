"use client";
import { Suspense } from "react";
import { CompareScreen } from "@/components/screens/CompareScreen";
export default function Page() {
  return (
    <Suspense fallback={<p className="empty">Loading</p>}>
      <CompareScreen />
    </Suspense>
  );
}
