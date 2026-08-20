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
    <main>
      <h1>DeepScout</h1>
      <p>Autonomous Research &amp; Decision Intelligence</p>
      <div className="card">
        <p>
          API status: <code>{apiStatus}</code>
        </p>
        <p>
          Phase 1 scaffold — research lifecycle UI arrives in Phase 7.
        </p>
      </div>
    </main>
  );
}
