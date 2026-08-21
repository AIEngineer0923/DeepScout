import { ResearchWorkspace } from "../components/ResearchWorkspace";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchHealth(): Promise<string> {
  try {
    const response = await fetch(`${apiUrl}/health`, { cache: "no-store" });
    if (!response.ok) return "unavailable";
    const data = (await response.json()) as { status: string };
    return data.status;
  } catch {
    return "unavailable";
  }
}

export default async function HomePage() {
  const apiStatus = await fetchHealth();

  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace">
        Skip to research workspace
      </a>
      <header className="site-header">
        <div className="brand">
          <p className="eyebrow">DeepScout</p>
          <h1>Research you can audit</h1>
        </div>
        <p className={`api-pill ${apiStatus === "ok" ? "ok" : "down"}`}>
          API {apiStatus === "ok" ? "connected" : "unavailable"}
        </p>
      </header>
      <main id="workspace">
        <p className="lede">
          Plan, search, fetch, verify, and report — with claims tied to real snapshots,
          not search snippets.
        </p>
        <ResearchWorkspace />
      </main>
    </div>
  );
}
