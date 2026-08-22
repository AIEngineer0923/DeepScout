export function truncateMarkdownBody(
  body: string,
  limit: number,
): { body: string; truncated: boolean } {
  if (body.length <= limit) return { body, truncated: false };
  const cut = body.lastIndexOf("\n\n", limit);
  const index = cut > limit * 0.4 ? cut : limit;
  return { body: body.slice(0, index), truncated: true };
}
