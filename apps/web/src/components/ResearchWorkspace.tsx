"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { safeHttpUrl } from "../lib/safe-url";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

type StreamEvent = {
  sequence: number;
  type: string;
  payload?: Record<string, unknown>;
};

type Workspace = {
  run_id: string;
  status: string;
  goal: string;
  termination_reason: string | null;
  llm_provider: string;
  llm_model: string;
  task_count: number;
  source_count: number;
  claim_count: number;
  evidence_count: number;
  contradiction_count: number;
  snapshot_count: number;
  consumed_sources: number;
  consumed_tool_calls: number;
  total_tokens: number | null;
  cost_usd: number | null;
  usage_status: string;
  cost_status: string;
  report_available: boolean;
  report_title: string | null;
  report_markdown: string | null;
  tasks: Array<{
    id: string;
    task_key: string;
    objective: string;
    status: string;
    depends_on: string[];
  }>;
  sources: Array<{ id: string; title: string; url: string; domain: string }>;
  claims: Array<{
    id: string;
    statement: string;
    verification_status: string;
  }>;
  evidence: Array<{ id: string; claim_id: string; quote: string }>;
  contradictions: Array<{ id: string; description: string }>;
  completed_phases: string[];
};

function formatUnknown(value: number | null, status?: string): string {
  if (value == null) return status === "unknown" || !status ? "Unknown" : "Unknown";
  return String(value);
}

export function ResearchWorkspace() {
  const [goal, setGoal] = useState(
    "Compare NMC and LFP EV battery chemistries and one practical trade-off.",
  );
  const [runId, setRunId] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (id: string) => {
    const response = await fetch(`${apiUrl}/api/v1/research-runs/${id}/workspace`);
    if (response.ok) {
      setWorkspace((await response.json()) as Workspace);
      return;
    }
    setError("Could not load this research run.");
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const existing = params.get("run");
    if (existing) {
      setRunId(existing);
      void refresh(existing);
    }
  }, [refresh]);

  useEffect(() => {
    if (!runId) return;
    const timer = setInterval(() => {
      void refresh(runId);
    }, 4000);
    return () => clearInterval(timer);
  }, [runId, refresh]);

  const phaseState = useMemo(() => {
    const completed = new Set<string>(workspace?.completed_phases ?? []);
    for (const event of events) {
      if (event.type === "phase.completed" && event.payload?.phase) {
        completed.add(String(event.payload.phase));
      }
    }
    return PHASE_ORDER.map((phase) => ({ phase, done: completed.has(phase) }));
  }, [events, workspace]);

  async function startRun() {
    setBusy(true);
    setError(null);
    setEvents([]);
    setWorkspace(null);
    try {
      const create = await fetch(`${apiUrl}/api/v1/research-runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal }),
      });
      if (!create.ok) throw new Error("Could not create the research run.");
      const created = (await create.json()) as { id: string; status: string };
      setRunId(created.id);

      const execute = await fetch(`${apiUrl}/api/v1/research-runs/${created.id}/execute`, {
        method: "POST",
      });
      if (!execute.ok) throw new Error("Could not start research.");

      const source = new EventSource(`${apiUrl}/api/v1/research-runs/${created.id}/events`);
      source.onmessage = (message) => {
        try {
          const parsed = JSON.parse(message.data) as StreamEvent;
          setEvents((prev) => [...prev.slice(-60), parsed]);
          void refresh(created.id);
        } catch {
          /* ignore malformed SSE payloads */
        }
      };
      source.onerror = () => source.close();
      void refresh(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function cancelRun() {
    if (!runId) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl}/api/v1/research-runs/${runId}/cancel`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("Could not cancel the run.");
      await refresh(runId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="panel">
        <h2>New research</h2>
        <label htmlFor="goal">What should DeepScout investigate?</label>
        <textarea
          id="goal"
          rows={4}
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
        />
        <div className="actions">
          <button type="button" onClick={startRun} disabled={busy || !goal.trim()}>
            {busy ? "Starting…" : "Start research"}
          </button>
          {runId ? (
            <button type="button" className="secondary" onClick={cancelRun} disabled={busy}>
              Cancel run
            </button>
          ) : null}
        </div>
        {error ? <p className="error">{error}</p> : null}
      </section>

      {!workspace && busy ? (
        <section className="panel" aria-busy="true" aria-live="polite">
          <h2>Starting research</h2>
          <p className="empty">Creating the run and waiting for the first persisted state.</p>
          <div className="skeleton" />
        </section>
      ) : null}

      {!workspace && !busy ? (
        <section className="panel empty" aria-live="polite">
          No run yet. Start a research goal to see tasks, sources, evidence, and the report.
        </section>
      ) : null}

      {workspace ? (
        <>
          <section className="panel" aria-live="polite">
            <div className="status-row">
              <span className={`badge ${workspace.status}`}>{workspace.status.replaceAll("_", " ")}</span>
              {workspace.termination_reason ? (
                <span className="badge">{workspace.termination_reason.replaceAll("_", " ")}</span>
              ) : null}
              <span className="meta">
                {workspace.llm_provider} · {workspace.llm_model}
              </span>
            </div>
            <p className="goal-text">{workspace.goal}</p>
            <div className="metric-grid">
              <Metric label="Tasks" value={workspace.task_count} />
              <Metric label="Sources" value={workspace.source_count} />
              <Metric label="Snapshots" value={workspace.snapshot_count} />
              <Metric label="Claims" value={workspace.claim_count} />
              <Metric label="Evidence" value={workspace.evidence_count} />
              <Metric
                label="Tokens"
                value={formatUnknown(workspace.total_tokens, workspace.usage_status)}
              />
              <Metric
                label="Cost USD"
                value={
                  workspace.cost_usd == null
                    ? "Unknown"
                    : workspace.cost_usd.toFixed(4)
                }
              />
            </div>
            <div className="phase-track">
              {phaseState.map(({ phase, done }) => (
                <span key={phase} className={done ? "phase done" : "phase"}>
                  {phase}
                </span>
              ))}
            </div>
          </section>

          <section className="panel">
            <h2>Tasks</h2>
            {workspace.tasks.length === 0 ? (
              <p className="empty">No tasks yet. The planner has not persisted a DAG.</p>
            ) : (
              <div className="stack">
                {workspace.tasks.map((task) => (
                  <article key={task.id} className="item-card">
                    <h3>{task.task_key}</h3>
                    <p>{task.objective}</p>
                    <div className="meta">
                      <span className={`badge ${task.status}`}>{task.status}</span>
                      {task.depends_on.length > 0 ? (
                        <span>depends on {task.depends_on.join(", ")}</span>
                      ) : (
                        <span>independent</span>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="panel">
            <h2>Sources & evidence</h2>
            {workspace.sources.length === 0 ? (
              <p className="empty">No sources yet. Search results appear after workers run.</p>
            ) : (
              <div className="stack">
                {workspace.sources.map((source) => {
                  const href = safeHttpUrl(source.url);
                  return (
                    <article key={source.id} className="item-card">
                      <h3>{source.title || source.domain || "Untitled source"}</h3>
                      <p>{source.domain}</p>
                      {href ? (
                        <a href={href} target="_blank" rel="noopener noreferrer">
                          {href}
                        </a>
                      ) : (
                        <p>Blocked or unsafe URL</p>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
            {workspace.claims.length === 0 && workspace.sources.length > 0 ? (
              <p className="empty">Sources collected. Claims appear after extract and verify.</p>
            ) : null}
            <div className="stack">
              {workspace.claims.map((claim) => {
                const quotes = workspace.evidence.filter((item) => item.claim_id === claim.id);
                return (
                  <article key={claim.id} className="item-card">
                    <h3>Claim</h3>
                    <p>{claim.statement}</p>
                    <div className="meta">
                      <span className={`badge ${claim.verification_status}`}>
                        {claim.verification_status.replaceAll("_", " ")}
                      </span>
                    </div>
                    {quotes.map((item) => (
                      <p key={item.id} className="quote">
                        “{item.quote}”
                      </p>
                    ))}
                  </article>
                );
              })}
            </div>
            {workspace.contradictions.length > 0 ? (
              <div className="stack">
                {workspace.contradictions.map((row) => (
                  <article key={row.id} className="item-card">
                    <h3>Contradiction</h3>
                    <p>{row.description}</p>
                  </article>
                ))}
              </div>
            ) : null}
          </section>

          <section className="panel">
            <h2>Report</h2>
            {workspace.report_available && workspace.report_markdown ? (
              <>
                <h3>{workspace.report_title || "Research report"}</h3>
                <p className="report-body">{workspace.report_markdown}</p>
              </>
            ) : (
              <p className="empty">
                No report yet. A report is written only after fetch/extract from collected
                sources, including after research-budget exhaustion when finalization is allowed.
              </p>
            )}
          </section>

          {events.length > 0 ? (
            <section className="panel">
              <h2>Activity</h2>
              <ol className="event-list">
                {events
                  .slice()
                  .reverse()
                  .map((event) => (
                    <li key={`${event.sequence}-${event.type}`}>
                      {event.type}
                      {event.payload?.phase ? ` · ${String(event.payload.phase)}` : ""}
                    </li>
                  ))}
              </ol>
            </section>
          ) : null}
        </>
      ) : null}
    </>
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
