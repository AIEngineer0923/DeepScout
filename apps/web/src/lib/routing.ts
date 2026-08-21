const UUID_SEGMENT = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export const PUBLIC_ENTRY_PATHS = new Set(["/", "/demo", "/login"]);

export function isPublicEntryPath(pathname: string): boolean {
  return PUBLIC_ENTRY_PATHS.has(pathname);
}

/** Read-only demo run workspace: /research/{uuid} and nested tabs. */
export function isDemoRunPath(pathname: string): boolean {
  const parts = pathname.split("/").filter(Boolean);
  if (parts[0] !== "research" || parts.length < 2) return false;
  if (parts[1] === "new" || parts[1] === "select") return false;
  return UUID_SEGMENT.test(parts[1]);
}

export function parseRunIdFromPath(pathname: string): string | null {
  const parts = pathname.split("/").filter(Boolean);
  if (parts[0] === "research" && parts[1] && UUID_SEGMENT.test(parts[1])) return parts[1];
  if (parts[0] === "resume" && parts[1] && UUID_SEGMENT.test(parts[1])) return parts[1];
  return null;
}
