"use client";

import { useEffect } from "react";
import { apiUrl } from "@/lib/api";

type VitalBody = {
  route: string;
  lcp_ms?: number;
  inp_ms?: number;
  cls?: number;
  ttfb_ms?: number;
  fcp_ms?: number;
  navigation_type: string;
  device_class: string;
  network_class: string;
  source: "field" | "lab";
};

function deviceClass(): string {
  if (typeof navigator === "undefined") return "unknown";
  const ua = navigator.userAgent;
  if (/Mobi|Android/i.test(ua)) return "mobile";
  return "desktop";
}

function networkClass(): string {
  const conn = (navigator as Navigator & { connection?: { effectiveType?: string } }).connection;
  return conn?.effectiveType ?? "unknown";
}

function post(body: VitalBody) {
  const payload: VitalBody = { ...body, source: body.source ?? "field" };
  void fetch(`${apiUrl}/api/v1/rum/vitals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    keepalive: true,
  }).catch(() => undefined);
}

export function startRum(source: "field" | "lab" = "field") {
  if (typeof window === "undefined" || typeof PerformanceObserver === "undefined") return;
  if (source === "field" && Math.random() > 0.2) return;
  const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
  const base = {
    route: window.location.pathname.slice(0, 128),
    navigation_type: nav?.type ?? "navigate",
    device_class: deviceClass(),
    network_class: networkClass(),
    source,
    ttfb_ms: nav ? Math.max(0, nav.responseStart) : undefined,
  };
  try {
    new PerformanceObserver((list) => {
      const last = list.getEntries().at(-1);
      if (last) post({ ...base, lcp_ms: last.startTime });
    }).observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver((list) => {
      const fcp = list.getEntries().find((entry) => entry.name === "first-contentful-paint");
      if (fcp) post({ ...base, fcp_ms: fcp.startTime });
    }).observe({ type: "paint", buffered: true });
    new PerformanceObserver((list) => {
      let cls = 0;
      for (const entry of list.getEntries() as Array<PerformanceEntry & { hadRecentInput?: boolean; value?: number }>) {
        if (!entry.hadRecentInput) cls += entry.value ?? 0;
      }
      post({ ...base, cls });
    }).observe({ type: "layout-shift", buffered: true });
    new PerformanceObserver((list) => {
      const last = list.getEntries().at(-1) as PerformanceEntry & { duration?: number };
      if (last?.duration != null) post({ ...base, inp_ms: last.duration });
    }).observe({ type: "event", buffered: true, durationThreshold: 16 } as PerformanceObserverInit);
  } catch {
    /* older browsers */
  }
}

export function RumCollector() {
  useEffect(() => {
    startRum(window.location.search.includes("perf_lab=1") ? "lab" : "field");
  }, []);
  return null;
}
