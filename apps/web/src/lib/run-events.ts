export type RunEventHandler = () => void;

function eventsUrl(base: string, lastId: string): string {
  const absolute = /^https?:\/\//i.test(base)
    ? base
    : `http://local.invalid${base.startsWith("/") ? base : `/${base}`}`;
  const parsed = new URL(absolute);
  parsed.searchParams.set("after", lastId);
  if (/^https?:\/\//i.test(base)) return parsed.toString();
  return `${parsed.pathname}${parsed.search}`;
}

/**
 * Reconnect EventSource after transient network loss without duplicating
 * ResearchRuns or HITL decisions (SSE is read-only). Replays from last id.
 */
export function connectRunEventSource(
  url: string,
  onMessage: RunEventHandler,
  options: { maxDelayMs?: number; coalesceMs?: number } = {},
): () => void {
  const maxDelay = options.maxDelayMs ?? 8000;
  const coalesceMs = options.coalesceMs ?? 120;
  let source: EventSource | null = null;
  let closed = false;
  let delay = 400;
  let lastId = "";
  let timer: ReturnType<typeof setTimeout> | null = null;
  let coalesce: ReturnType<typeof setTimeout> | null = null;

  const bump = () => {
    if (coalesce) return;
    coalesce = setTimeout(() => {
      coalesce = null;
      onMessage();
    }, coalesceMs);
  };

  const open = () => {
    if (closed) return;
    source = new EventSource(lastId ? eventsUrl(url, lastId) : url);
    source.onmessage = (ev: MessageEvent) => {
      delay = 400;
      if (ev.lastEventId) lastId = ev.lastEventId;
      bump();
    };
    source.onerror = () => {
      source?.close();
      source = null;
      if (closed) return;
      timer = setTimeout(() => {
        delay = Math.min(delay * 2, maxDelay);
        open();
      }, delay);
    };
  };

  open();
  return () => {
    closed = true;
    if (timer) clearTimeout(timer);
    if (coalesce) clearTimeout(coalesce);
    source?.close();
  };
}

export { eventsUrl };
