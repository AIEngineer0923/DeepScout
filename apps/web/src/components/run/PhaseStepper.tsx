import { phaseLabel } from "@/lib/format";

const PHASES = ["plan", "research", "verify", "synthesis", "report"] as const;

export function PhaseStepper({
  completed,
  status,
}: {
  completed: string[];
  status: string;
}) {
  const mapped = completed.map((phase) =>
    ["fetch", "extract"].includes(phase) ? "research" : ["contradiction", "critic"].includes(phase) ? "verify" : phase,
  );
  const current = status === "completed" ? "report" : mapped[mapped.length - 1] ?? "plan";
  return (
    <ol className="stepper" aria-label="Research phases">
      {PHASES.map((phase) => {
        const done = mapped.includes(phase) && phase !== current;
        const active = phase === current && status !== "completed";
        const finished = status === "completed" || (done && !active);
        return (
          <li key={phase} className={`step ${finished ? "done" : ""} ${active ? "active" : ""}`}>
            <div className="name">{phaseLabel(phase)}</div>
            <div className="meta">{finished ? "Completed" : active ? "Running" : "Pending"}</div>
          </li>
        );
      })}
    </ol>
  );
}
