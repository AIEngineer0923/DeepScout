"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, apiUrl } from "@/lib/api";
import { connectRunEventSource } from "@/lib/run-events";
import type { Workspace } from "@/lib/types";
import { useDemoReadOnly } from "@/components/DemoReadOnlyContext";

type Ctx = {
  workspace: Workspace | null;
  error: string | null;
  reload: () => void;
};

const RunContext = createContext<Ctx>({ workspace: null, error: null, reload: () => undefined });

export function RunProvider({ runId, children }: { runId: string; children: React.ReactNode }) {
  const demoReadOnly = useDemoReadOnly();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    api.workspace(runId).then(setWorkspace).catch((err: Error) => setError(err.message));
  }, [runId]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    if (demoReadOnly) {
      return undefined;
    }
    const stop = connectRunEventSource(`${apiUrl}/api/v1/research-runs/${runId}/events`, () => {
      api.workspace(runId).then((next) => {
        setWorkspace((prev) => {
          if (prev && prev.event_head === next.event_head && prev.status === next.status) {
            return prev;
          }
          return next;
        });
      }).catch(() => undefined);
    });
    return stop;
  }, [demoReadOnly, runId]);

  const value = useMemo(() => ({ workspace, error, reload }), [workspace, error, reload]);
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRun() {
  return useContext(RunContext);
}
