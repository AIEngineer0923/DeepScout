"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, apiUrl } from "@/lib/api";
import type { Workspace } from "@/lib/types";

type Ctx = {
  workspace: Workspace | null;
  error: string | null;
  reload: () => void;
};

const RunContext = createContext<Ctx>({ workspace: null, error: null, reload: () => undefined });

export function RunProvider({ runId, children }: { runId: string; children: React.ReactNode }) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    api.workspace(runId).then(setWorkspace).catch((err: Error) => setError(err.message));
  }, [runId]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    const source = new EventSource(`${apiUrl}/api/v1/research-runs/${runId}/events`);
    source.onmessage = () => {
      api.workspace(runId).then(setWorkspace).catch(() => undefined);
    };
    source.onerror = () => source.close();
    return () => source.close();
  }, [runId]);

  const value = useMemo(() => ({ workspace, error, reload }), [workspace, error, reload]);
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRun() {
  return useContext(RunContext);
}
