"use client";

import { useT } from "@/i18n/context";

const PHASES = ["plan", "research", "verify", "synthesis", "report"] as const;

export function PhaseStepper({
  completed,
  status,
}: {
  completed: string[];
  status: string;
}) {
  const t = useT();
  const mapped = completed.map((phase) =>
    ["fetch", "extract"].includes(phase) ? "research" : ["contradiction", "critic"].includes(phase) ? "verify" : phase,
  );
  const current = status === "completed" ? "report" : mapped[mapped.length - 1] ?? "plan";
  return (
    <ol className="stepper" aria-label={t("nav.research")}>
      {PHASES.map((phase) => {
        const done = mapped.includes(phase) && phase !== current;
        const active = phase === current && status !== "completed";
        const finished = status === "completed" || (done && !active);
        return (
          <li key={phase} className={`step ${finished ? "done" : ""} ${active ? "active" : ""}`}>
            <div className="name">{t(`phase.${phase}`)}</div>
            <div className="meta">{finished ? t("phase.completed") : active ? t("phase.running") : t("phase.pending")}</div>
          </li>
        );
      })}
    </ol>
  );
}
