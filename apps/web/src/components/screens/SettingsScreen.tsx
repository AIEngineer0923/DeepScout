"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const TABS = ["General", "Models & Providers", "Research", "Quality & Evaluation", "Integrations", "Security", "Notifications", "Advanced"];

export function SettingsScreen() {
  const [tab, setTab] = useState("General");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    api.settings().then(setData).catch(() => setData(null));
  }, []);
  const providers = (data?.providers ?? {}) as Record<string, { configured?: boolean; model?: string }>;
  const langsmith = (data?.langsmith ?? {}) as { connected?: boolean; project?: string; region?: string };
  const defaults = (data?.research_defaults ?? {}) as Record<string, unknown>;
  const health = (data?.health ?? {}) as Record<string, string>;
  const identity = (data?.identity ?? {}) as { label?: string; role?: string };
  return (
    <div>
      <h1 className="page-title">Settings</h1>
      <p className="page-sub">Only settings with real backend semantics are shown. No fake billing, quotas, or accounts.</p>
      <div className="tabs">
        {TABS.map((item) => (
          <button key={item} className={`tab ${tab === item ? "active" : ""}`} onClick={() => setTab(item)}>{item}</button>
        ))}
      </div>
      <div className="grid cols-2">
        <section className="card">
          {tab === "General" ? (
            <>
              <h2>Workspace</h2>
              <p>{identity.label} · {identity.role}</p>
              <p>Language: English (UI)</p>
              <p className="muted">There is no multi-user workspace. Identity is local/operator.</p>
            </>
          ) : null}
          {tab === "Models & Providers" ? (
            <>
              <h2>Providers</h2>
              {Object.entries(providers).map(([name, value]) => (
                <p key={name}>{name}: {value.configured ? "configured" : "not configured"}{value.model ? ` · ${value.model}` : ""}</p>
              ))}
              <p className="muted">API keys are never displayed.</p>
              <h2>Model routing</h2>
              <p>Automatic via ModelRouter. Default provider from environment.</p>
            </>
          ) : null}
          {tab === "Research" ? (
            <>
              <h2>Research defaults</h2>
              <p>Max iterations: {String(defaults.max_iterations)}</p>
              <p>Max sources: {String(defaults.max_sources)}</p>
              <p>Max tool calls: {String(defaults.max_tool_calls)}</p>
              <p>Durable LangGraph checkpoint: {String(defaults.durable_checkpoint)}</p>
              <p className="muted">{String(defaults.concurrency_note)}</p>
            </>
          ) : null}
          {tab === "Quality & Evaluation" ? (
            <>
              <h2>Evaluations</h2>
              <p>Deterministic evaluators run against real artifacts.</p>
              <p>LLM judges are offline-only in development (0% online sampling).</p>
            </>
          ) : null}
          {tab === "Integrations" ? (
            <>
              <h2>LangSmith</h2>
              <p>Status: {langsmith.connected ? "Connected" : "Not configured"}</p>
              <p>Project: {langsmith.project}</p>
              <p>Region: {langsmith.region}</p>
            </>
          ) : null}
          {tab === "Security" ? (
            <>
              <h2>Privacy / security</h2>
              <p>{String((data?.security as { untrusted_content?: string } | undefined)?.untrusted_content)}</p>
              <p>{String((data?.security as { ssrf?: string } | undefined)?.ssrf)}</p>
            </>
          ) : null}
          {tab === "Notifications" ? <p className="muted">No notification backend is configured. This tab is informational only.</p> : null}
          {tab === "Advanced" ? (
            <>
              <h2>System status</h2>
              {Object.entries(health).map(([key, value]) => (
                <p key={key}>{key}: {value}</p>
              ))}
              <p className="muted">Vector store is not in scope for this pre-RAG gate.</p>
            </>
          ) : null}
        </section>
        <aside className="drawer">
          <h2>System status</h2>
          {Object.entries(health).map(([key, value]) => (
            <p key={key}>{key}: {value}</p>
          ))}
          <p className="muted">No Professional plan, token quota, or tenant settings exist in this product.</p>
        </aside>
      </div>
    </div>
  );
}
