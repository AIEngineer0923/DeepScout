# API / SSE Architecture

## REST endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/research-runs` | Create a research run |
| `GET` | `/api/v1/research-runs/{id}` | Run status + summary |
| `GET` | `/api/v1/research-runs/{id}/workspace` | Owner or sanitized public workspace |
| `GET` | `/api/v1/research-runs/{id}/events` | SSE progress stream |
| `GET` | `/api/v1/research-runs/{id}/snapshots/{snapshotId}` | Owner or sanitized snapshot presentation |

## SSE event types

| Event | Payload |
|---|---|
| `run.started` | run_id, goal, budget |
| `phase.started` | phase name, iteration |
| `phase.progress` | operational message (no CoT) |
| `source.collected` | source metadata |
| `claim.extracted` | claim summary + verification state |
| `contradiction.detected` | contradiction summary |
| `decision.ready` | decision preview |
| `report.ready` | report URL/id |
| `run.failed` | error code (no secrets) |
| `run.completed` | summary stats |

## Security

- No API keys or raw LLM reasoning in responses.
- MODE B authorizes the run before opening a stream and returns 404 for cross-tenant access.
- Open hosted streams revalidate the session and owner during every loop, so logout/revocation
  terminates access.
- Replay is capped at 200 events per database query and concurrent streams are bounded per
  identity.
- The built-in rate limiter is bounded and process-local; multi-instance deployments require a
  distributed edge/gateway limit.
- Public demos cannot open SSE streams.

## Frontend consumption

The Next.js frontend consumes the same-origin SSE endpoint under `apps/web/`. PostgreSQL LISTEN/
NOTIFY wakes readers; persisted `research_run_events` remain the replay authority.
