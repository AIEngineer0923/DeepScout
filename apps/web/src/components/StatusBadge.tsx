import { statusTone } from "@/lib/format";

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${statusTone(status)}`}>
      <span className={`dot ${statusTone(status)}`} />
      {status.replaceAll("_", " ")}
    </span>
  );
}
