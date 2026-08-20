# ADR-005: SSE streaming

**Status:** Accepted (Phase 0)

## Context

UI needs real-time operational progress without exposing model chain-of-thought.

## Decision

FastAPI Server-Sent Events with typed operational events.

## Consequences

- Simple unidirectional streaming
- WebSockets deferred unless proven necessary
