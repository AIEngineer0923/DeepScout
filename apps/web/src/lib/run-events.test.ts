import { afterEach, describe, expect, it, vi } from "vitest";
import { connectRunEventSource, eventsUrl } from "./run-events";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
}

describe("connectRunEventSource", () => {
  afterEach(() => {
    FakeEventSource.instances = [];
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("reconnects after error without leaving the previous source open", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.useFakeTimers();
    const onMessage = vi.fn();
    const stop = connectRunEventSource("http://example/events", onMessage, { maxDelayMs: 500 });
    expect(FakeEventSource.instances).toHaveLength(1);
    FakeEventSource.instances[0].onerror?.();
    expect(FakeEventSource.instances[0].closed).toBe(true);
    vi.advanceTimersByTime(400);
    expect(FakeEventSource.instances).toHaveLength(2);
    stop();
    expect(FakeEventSource.instances[1].closed).toBe(true);
  });

  it("replays from lastEventId on reconnect", () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.useFakeTimers();
    const stop = connectRunEventSource("http://example/events", vi.fn(), {
      maxDelayMs: 500,
      coalesceMs: 0,
    });
    FakeEventSource.instances[0].onmessage?.({ lastEventId: "7", data: "{}" } as MessageEvent);
    vi.advanceTimersByTime(1);
    FakeEventSource.instances[0].onerror?.();
    vi.advanceTimersByTime(400);
    expect(FakeEventSource.instances[1].url).toContain("after=7");
    stop();
  });
});

describe("eventsUrl", () => {
  it("keeps origin for absolute URLs", () => {
    expect(eventsUrl("http://127.0.0.1:8000/api/v1/research-runs/abc/events", "3")).toBe(
      "http://127.0.0.1:8000/api/v1/research-runs/abc/events?after=3",
    );
  });
});
