"use client";
import { Suspense } from "react";
import { ClaimsScreen } from "@/components/screens/ClaimsScreen";
export default function Page() {
  return <Suspense fallback={<p className="empty">Loading claims…</p>}><ClaimsScreen /></Suspense>;
}
