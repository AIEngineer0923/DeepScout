# HTTP / reverse-proxy contract

DeepScout's supported posture is local or trusted-network (MODE A). This document exists so operators do not invent unsafe proxy defaults.

## Trust

The API **does not** trust `X-Forwarded-For`, `X-Forwarded-Proto`, or `Forwarded` from arbitrary clients.

If a reverse proxy is used:

- Terminate TLS at the proxy.
- Set `API_HOST=127.0.0.1` (or a private overlay) so the app is not reachable except through the proxy.
- Forward only from the proxy's network. Do not enable Starlette `ProxyHeadersMiddleware` against the public Internet without a tight `trusted_hosts` / trusted proxy CIDR list.
- Rate-limit client IP at the proxy. In-process DeepScout limits use `request.client.host`, which is the direct TCP peer (the proxy) unless the runtime is configured to trust forwarded headers.

## Required proxy behavior

| Topic | Contract |
|---|---|
| HTTPS | Required for any non-loopback operator access |
| HSTS | Set on the proxy for HTTPS; the API emits HSTS only when the request scheme is already `https` |
| Host | Reject unknown hosts at the proxy; do not reflect untrusted Host into redirects |
| Request size | Align with `MAX_REQUEST_BYTES` (default 1_000_000) |
| Timeouts | SSE `/events` must not be buffered; idle timeouts should exceed research run duration or reconnect |
| SSE | `X-Accel-Buffering: no`; disable proxy response buffering for `text/event-stream` |
| CORS | Exact operator origins only; never `*` |
| CSP | Frontend sets document CSP; API sets `default-src 'none'` on JSON responses |
| Server tokens | Do not advertise framework versions at the edge |

## DeepScout will not

- Authenticate users
- Authorize object access beyond "the caller reached this URL"
- Treat rate limits as authorization
- Enable HSTS on plain HTTP localhost
