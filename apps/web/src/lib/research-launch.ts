import { api, type ResearchPreferencesPayload } from "./api";
import { rememberRunId } from "./current-run";

export type ResearchMode = "quick" | "standard" | "deep";

export type ResearchLaunchInput = {
  goal: string;
  research_mode: ResearchMode;
  output_language: string;
  preferences?: ResearchPreferencesPayload;
};

export const DEFAULT_RESEARCH_PREFERENCES: ResearchPreferencesPayload = {
  geographic_focus: { mode: "automatic", regions: [] },
  freshness: { mode: "automatic", policy: "any" },
  model_policy: { mode: "automatic", provider: null, model: null },
  excluded_domains: [],
};

/** Create and enqueue a run through the same product path from every research entry point. */
export async function launchResearch(input: ResearchLaunchInput): Promise<string> {
  const created = await api.createRun({
    ...input,
    goal: input.goal.trim(),
    preferences: input.preferences ?? DEFAULT_RESEARCH_PREFERENCES,
  });
  rememberRunId(created.id);
  await api.execute(created.id);
  return created.id;
}
