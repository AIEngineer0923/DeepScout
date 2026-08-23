"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { clearLastRunId } from "@/lib/current-run";
import { useI18n } from "@/i18n/context";

const PROVIDERS = ["google", "openai", "anthropic", "tavily", "langsmith"] as const;

type AccountData = {
  credential_source?: "ENV" | "USER_VAULT";
  credentials?: Array<{ provider?: string; configured?: boolean }>;
};

export default function AccountPage() {
  const { t } = useI18n();
  const [account, setAccount] = useState<AccountData | null>(null);
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    api.account()
      .then((value) => setAccount(value as AccountData))
      .catch((err) => setError(err instanceof Error ? err.message : t("account.loadFailed")));
  }, [t]);

  async function save(provider: string) {
    const value = secrets[provider]?.trim();
    if (!value) return;
    setBusy(provider);
    setError("");
    try {
      await api.saveCredential(provider, value);
      setSecrets((current) => ({ ...current, [provider]: "" }));
      setMessage(t("account.saved"));
      setAccount((await api.account()) as AccountData);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("account.saveFailed"));
    } finally {
      setBusy(null);
    }
  }

  async function logout() {
    setError("");
    try {
      await api.logout();
      clearLastRunId();
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : t("account.actionFailed"));
    }
  }

  async function exportData() {
    setError("");
    try {
      const payload = await api.exportAccount();
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "deepscout-account-export.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("account.actionFailed"));
    }
  }

  async function logoutAll() {
    setError("");
    try {
      await api.logoutAll();
      clearLastRunId();
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : t("account.actionFailed"));
    }
  }

  async function deleteAccount() {
    if (!window.confirm(t("account.deleteConfirm"))) return;
    setError("");
    try {
      await api.deleteAccount();
      clearLastRunId();
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : t("account.actionFailed"));
    }
  }

  const credentials = account?.credentials ?? [];
  const hosted = account?.credential_source === "USER_VAULT";

  if (!account) {
    if (!error) return <p className="empty">{t("landing.loading")}</p>;
    return (
      <section className="card" style={{ maxWidth: 560 }} role="alert">
        <h1 className="page-title">{t("account.title")}</h1>
        <p className="error">{error}</p>
        <button
          type="button"
          className="btn primary"
          onClick={() => {
            setError("");
            api.account()
              .then((value) => setAccount(value as AccountData))
              .catch((err) => setError(err instanceof Error ? err.message : t("account.loadFailed")));
          }}
        >
          {t("action.retry")}
        </button>
      </section>
    );
  }

  return (
    <div className="grid" style={{ gap: 22, maxWidth: 720 }}>
      <div className="page-head">
        <h1 className="page-title">{t("account.title")}</h1>
        <p className="page-sub">{t("account.subtitle")}</p>
      </div>
      <section className="card">
        <h2>{t("account.providers")}</h2>
        <p className="page-sub">{hosted ? t("account.privacyHosted") : t("account.privacyLocal")}</p>
        {!hosted ? <p className="note-box">{t("account.localCredentialsHelp")}</p> : null}
        {PROVIDERS.map((provider) => {
          const row = credentials.find((item) => item.provider === provider);
          return (
            <div key={provider} style={{ marginTop: 16 }}>
              <label htmlFor={`cred-${provider}`}>
                {provider} — {row?.configured ? t("configured") : t("notConfigured")}
              </label>
              {hosted ? (
                <>
                  <input
                    id={`cred-${provider}`}
                    className="input"
                    type="password"
                    autoComplete="off"
                    value={secrets[provider] ?? ""}
                    placeholder={row?.configured ? t("account.replaceSecret") : t("account.pasteSecret")}
                    onChange={(event) => setSecrets((current) => ({ ...current, [provider]: event.target.value }))}
                  />
                  <button type="button" className="btn" style={{ marginTop: 8 }} disabled={busy === provider || !(secrets[provider]?.trim())} onClick={() => void save(provider)}>
                    {t("action.save")}
                  </button>
                </>
              ) : null}
            </div>
          );
        })}
        {message ? <p className="badge ok">{message}</p> : null}
        {error ? <p className="error" role="alert">{error}</p> : null}
      </section>
      <section className="card">
        <h2>{t("account.data")}</h2>
        <button
          type="button"
          className="btn"
          onClick={() => void exportData()}
        >
          {t("account.export")}
        </button>
      </section>
      {hosted ? <section className="card">
        <h2>{t("account.security")}</h2>
        <button type="button" className="btn" onClick={() => void logout()}>
          {t("nav.signOut")}
        </button>
        <button
          type="button"
          className="btn"
          style={{ marginLeft: 8 }}
          onClick={() => void logoutAll()}
        >
          {t("account.logoutAll")}
        </button>
        <button
          type="button"
          className="btn"
          style={{ marginLeft: 8 }}
          onClick={() => void deleteAccount()}
        >
          {t("account.delete")}
        </button>
      </section> : null}
    </div>
  );
}
