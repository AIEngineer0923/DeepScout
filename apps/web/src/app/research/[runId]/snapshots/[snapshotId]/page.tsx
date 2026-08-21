"use client";
import { SnapshotScreen } from "@/components/screens/SnapshotScreen";
import { useParams } from "next/navigation";
export default function Page() {
  const params = useParams<{ snapshotId: string }>();
  return <SnapshotScreen snapshotId={params.snapshotId} />;
}
