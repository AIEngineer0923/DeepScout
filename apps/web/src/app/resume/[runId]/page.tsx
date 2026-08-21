"use client";
import { RunProvider } from "@/components/run/RunProvider";
import { ResumeScreen } from "@/components/screens/ResumeScreen";
import { useParams } from "next/navigation";
export default function Page() {
  const params = useParams<{ runId: string }>();
  return <RunProvider runId={params.runId}><ResumeScreen /></RunProvider>;
}
