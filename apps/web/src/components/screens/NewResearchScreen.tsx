"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const MODES = [
  { id: "quick", title: "Quick", body: "Fast overview, essential sources, lower cost." },
  { id: "standard", title: "Standard", body: "Balanced, verifiable research." },
  { id: "deep", title: "Deep", body: "Comprehensive analysis, higher cost." },
] as const;

export function NewResearchScreen() {
  const router = useRouter();
  const [goal, setGoal] = useState("");
  const [mode, setMode] = useState<"quick" | "standard" | "deep">("standard");
  const [language, setLanguage] = useState("English");
  const [freshness, setFreshness] = useState("Last 12 months");
  const [excluded, setExcluded] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [maxSources, setMaxSources] = useState("20");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const summary = useMemo(
    () => ({
      mode,
      language,
      freshness,
      sources: mode === "quick" ? "4–8" : mode === "deep" ? "20–60" : "8–20",
      cost: "Unknown until the run reports usage",
    }),
    [mode, language, freshness],
  );

  async function start() {
    if (!goal.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.createRun({ goal: goal.trim(), research_mode: mode });
      await api.execute(created.id);
      router.push(`/research/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start research");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid cols-2">
      <div>
        <h1 className="page-title">New Research</h1>
        <p className="page-sub">Define a research goal. DeepScout plans tasks dynamically from that goal.</p>
        <div className="card" style={{ marginTop: 16 }}>
          <div className="field">
            <label htmlFor="goal">1. What do you want to research?</label>
            <textarea id="goal" className="textarea" maxLength={1000} value={goal} onChange={(e) => setGoal(e.target.value)} />
            <span className="muted">{goal.length} / 1000</span>
          </div>
          <div style={{ marginTop: 16 }}>
            <div className="muted">2. Research mode</div>
            <div className="mode-grid" style={{ marginTop: 8 }}>
              {MODES.map((item) => (
                <button key={item.id} type="button" className={`mode ${mode === item.id ? "selected" : ""}`} onClick={() => setMode(item.id)}>
                  <strong>{item.title}</strong>
                  <div className="muted">{item.body}</div>
                </button>
              ))}
            </div>
          </div>
          <div className="grid cols-2" style={{ marginTop: 16 }}>
            <div className="field"><label>Language</label><input className="input" value={language} onChange={(e) => setLanguage(e.target.value)} /></div>
            <div className="field"><label>Source freshness</label><input className="input" value={freshness} onChange={(e) => setFreshness(e.target.value)} /></div>
            <div className="field"><label>Excluded domains</label><input className="input" value={excluded} onChange={(e) => setExcluded(e.target.value)} placeholder="None" /></div>
            <div className="field"><label>Region focus</label><input className="input" value="Any region" readOnly /></div>
          </div>
          <button type="button" className="btn ghost" style={{ marginTop: 12 }} onClick={() => setAdvanced(!advanced)}>
            {advanced ? "Hide" : "Show"} advanced settings
          </button>
          {advanced ? (
            <div className="field" style={{ marginTop: 8 }}>
              <label>Max sources (hint — actual limit comes from server budget for this mode)</label>
              <input className="input" value={maxSources} onChange={(e) => setMaxSources(e.target.value)} />
            </div>
          ) : null}
          {error ? <p className="badge bad wrap-text">{error}</p> : null}
          <div className="row" style={{ marginTop: 16, justifyContent: "space-between" }}>
            <button className="btn" type="button" onClick={() => router.push("/")}>Cancel</button>
            <button className="btn primary" type="button" disabled={busy || !goal.trim()} onClick={() => void start()}>Start research →</button>
          </div>
        </div>
      </div>
      <aside>
        <section className="card">
          <h2>Research summary</h2>
          <p className="wrap-text">{goal || "Goal will appear here as you type."}</p>
          <p>Mode: {summary.mode}</p>
          <p>Expected sources: {summary.sources}</p>
          <p>Language: {summary.language}</p>
          <p>Freshness: {summary.freshness}</p>
        </section>
        <section className="card" style={{ marginTop: 16 }}>
          <h2>Resource estimate</h2>
          <p>Estimated cost: <strong>{summary.cost}</strong></p>
          <p className="muted">DeepScout does not invent token or dollar estimates before a run. Cost is shown after real usage is mapped to the pricing catalog, otherwise Unknown.</p>
        </section>
      </aside>
    </div>
  );
}
