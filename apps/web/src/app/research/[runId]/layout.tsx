"use client";

import { RunProvider } from "@/components/run/RunProvider";
import { useParams } from "next/navigation";

export default function RunLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ runId: string }>();
  return <RunProvider runId={params.runId}>{children}</RunProvider>;
}
