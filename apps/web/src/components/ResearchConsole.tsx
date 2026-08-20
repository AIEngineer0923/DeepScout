"use client";

import { useState } from "react";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RunResponse = {
  id: string;
  status: string;
  goal: string;
};

export function ResearchConsole() {
  const [goal, setGoal] = useState(
    "What are two commonly used EV battery chemistries and one trade-off between them?",
  );
  const [run, setRun] = useState<RunResponse | null>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function startRun() {
    setBusy(true);
    setError(null);
    setEvents([]);
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
        setEvents((prev) => [...prev.slice(-40), message.data]);
      };
      source.onerror = () => source.close();
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
      <button type="button" onClick={startRun} disabled={busy || !goal.trim()}>
        {busy ? "Starting…" : "Start research"}
      </button>
      {error ? <p className="error">{error}</p> : null}
      {run ? (
        <p>
          Run <code>{run.id}</code> — status <code>{run.status}</code>
        </p>
      ) : null}
      {events.length > 0 ? (
        <pre className="events">{events.join("\n")}</pre>
      ) : null}
    </section>
  );
}
