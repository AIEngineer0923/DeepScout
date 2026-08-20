"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RunResponse = {
  id: string;
  status: string;
  goal: string;
};

type StreamEvent = {
  sequence: number;
  type: string;
  payload?: Record<string, unknown>;
  created_at?: string;
};

type RunSummary = {
  run_id: string;
  status: string;
  goal: string;
  termination_reason: string | null;
  task_count: number;
  source_count: number;
  claim_count: number;
  evidence_count: number;
  contradiction_count: number;
  consumed_sources: number;
  consumed_tool_calls: number;
  total_tokens: number | null;
  cost_usd: number | null;
  usage_status: string;
  cost_status: string;
};

const PHASE_ORDER = [
  "plan",
  "research",
  "fetch",
  "extract",
  "verify",
  "contradiction",
  "critic",
  "synthesis",
  "report",
];

export function ResearchConsole() {
  const [goal, setGoal] = useState(
    "What are two commonly used EV battery chemistries and one trade-off between them?",
  );
  const [run, setRun] = useState<RunResponse | null>(null);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshSummary = useCallback(async (runId: string) => {
    const response = await fetch(`${apiUrl}/api/v1/research-runs/${runId}/summary`);
    if (response.ok) {
      setSummary((await response.json()) as RunSummary);
    }
  }, []);

  useEffect(() => {
    if (!run?.id) return;
    const timer = setInterval(() => {
      void refreshSummary(run.id);
    }, 3000);
    return () => clearInterval(timer);
  }, [run?.id, refreshSummary]);

  const phaseState = useMemo(() => {
    const completed = new Set<string>();
    for (const event of events) {
      if (event.type === "phase.completed" && event.payload?.phase) {
        completed.add(String(event.payload.phase));
      }
    }
    return PHASE_ORDER.map((phase) => ({
      phase,
      done: completed.has(phase),
    }));
  }, [events]);

  async function startRun() {
    setBusy(true);
    setError(null);
    setEvents([]);
    setSummary(null);
    try {
      const create = await fetch(`${apiUrl}/api/v1/research-runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal }),
      });
      if (!create.ok) throw new Error(`Create failed (${create.status})`);
      const created = (await create.json()) as RunResponse;
      setRun(created);

      const execute = await fetch(`${apiUrl}/api/v1/research-runs/${created.id}/execute`, {
        method: "POST",
      });
      if (!execute.ok) throw new Error(`Execute failed (${execute.status})`);

      const source = new EventSource(`${apiUrl}/api/v1/research-runs/${created.id}/events`);
      source.onmessage = (message) => {
        try {
          const parsed = JSON.parse(message.data) as StreamEvent;
          setEvents((prev) => [...prev.slice(-80), parsed]);
          void refreshSummary(created.id);
        } catch {
          setEvents((prev) => [
            ...prev.slice(-80),
            { sequence: prev.length + 1, type: "parse.error", payload: { raw: message.data } },
          ]);
        }
      };
      source.onerror = () => source.close();
      void refreshSummary(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  async function cancelRun() {
    if (!run) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl}/api/v1/research-runs/${run.id}/cancel`, {
        method: "POST",
      });
      if (!response.ok) throw new Error(`Cancel failed (${response.status})`);
      const updated = (await response.json()) as RunResponse;
      setRun(updated);
      await refreshSummary(run.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>Research Run</h2>
      <label htmlFor="goal">Goal</label>
      <textarea
        id="goal"
        rows={4}
        value={goal}
        onChange={(event) => setGoal(event.target.value)}
      />
      <div className="actions">
        <button type="button" onClick={startRun} disabled={busy || !goal.trim()}>
          {busy ? "Working…" : "Start research"}
        </button>
        {run ? (
          <button type="button" className="secondary" onClick={cancelRun} disabled={busy}>
            Cancel run
          </button>
        ) : null}
      </div>
      {error ? <p className="error">{error}</p> : null}
      {run ? (
        <p>
          Run <code>{run.id}</code> — status <code>{run.status}</code>
        </p>
      ) : null}

      {summary ? (
        <div className="dashboard">
          <div className="metric-grid">
            <Metric label="Tasks" value={summary.task_count} />
            <Metric label="Sources" value={summary.source_count} />
            <Metric label="Claims" value={summary.claim_count} />
            <Metric label="Evidence" value={summary.evidence_count} />
            <Metric label="Contradictions" value={summary.contradiction_count} />
            <Metric
              label="Tokens"
              value={summary.total_tokens ?? "UNKNOWN"}
            />
            <Metric
              label="Cost USD"
              value={summary.cost_usd ?? "UNKNOWN"}
            />
          </div>
          <div className="phase-track">
            {phaseState.map(({ phase, done }) => (
              <span key={phase} className={done ? "phase done" : "phase"}>
                {phase}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {events.length > 0 ? (
        <ul className="event-list">
          {events
            .slice()
            .reverse()
            .map((event) => (
              <li key={`${event.sequence}-${event.type}`}>
                <strong>{event.type}</strong>
                {event.payload ? (
                  <code>{JSON.stringify(event.payload)}</code>
                ) : null}
              </li>
            ))}
        </ul>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
    </div>
  );
}
