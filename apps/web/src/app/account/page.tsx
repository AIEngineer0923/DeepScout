"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { clearLastRunId } from "@/lib/current-run";

const PROVIDERS = ["google", "openai", "anthropic", "tavily", "langsmith"] as const;

export default function AccountPage() {
  const [account, setAccount] = useState<Record<string, unknown> | null>(null);
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.account().then(setAccount).catch(() => setAccount(null));
  }, []);

  async function save(provider: string) {
    const value = secrets[provider]?.trim();
    if (!value) return;
    await api.saveCredential(provider, value);
    setSecrets((current) => ({ ...current, [provider]: "" }));
    setMessage("Configured");
    setAccount(await api.account());
  }

  async function logout() {
    await api.logout();
    clearLastRunId();
    window.location.href = "/";
  }

  const credentials = (account?.credentials as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <div className="grid" style={{ gap: 22, maxWidth: 720 }}>
      <div className="page-head">
        <h1 className="page-title">Account</h1>
        <p className="page-sub">Profile, providers, and privacy. No subscriptions.</p>
      </div>
      <section className="card">
        <h2>Providers</h2>
        <p className="page-sub">{String(account?.privacy ?? "")}</p>
        {PROVIDERS.map((provider) => {
          const row = credentials.find((item) => item.provider === provider);
          return (
            <div key={provider} style={{ marginTop: 16 }}>
              <label htmlFor={`cred-${provider}`}>
                {provider} — {row?.configured ? "Configured" : "Not configured"}
              </label>
              <input
                id={`cred-${provider}`}
                className="input"
                type="password"
                autoComplete="off"
                value={secrets[provider] ?? ""}
                placeholder={row?.configured ? "Replace secret" : "Paste secret"}
                onChange={(event) => setSecrets((current) => ({ ...current, [provider]: event.target.value }))}
              />
              <button type="button" className="btn" style={{ marginTop: 8 }} onClick={() => void save(provider)}>
                Save
              </button>
            </div>
          );
        })}
        {message ? <p>{message}</p> : null}
      </section>
      <section className="card">
        <h2>Privacy / Data</h2>
        <button
          type="button"
          className="btn"
          onClick={async () => {
            const payload = await api.exportAccount();
            const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = "deepscout-account-export.json";
            link.click();
            URL.revokeObjectURL(url);
          }}
        >
          Export my data
        </button>
      </section>
      <section className="card">
        <h2>Security</h2>
        <button type="button" className="btn" onClick={() => void logout()}>
          Log out
        </button>
        <button
          type="button"
          className="btn"
          style={{ marginLeft: 8 }}
          onClick={async () => {
            await api.logoutAll();
            clearLastRunId();
            window.location.href = "/";
          }}
        >
          Log out all sessions
        </button>
        <button
          type="button"
          className="btn"
          style={{ marginLeft: 8 }}
          onClick={async () => {
            if (!window.confirm("Delete this account and all owned research?")) return;
            await api.deleteAccount();
            clearLastRunId();
            window.location.href = "/";
          }}
        >
          Delete account
        </button>
      </section>
    </div>
  );
}
