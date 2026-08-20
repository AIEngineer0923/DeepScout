# Secure Fetch Pipeline

**Must be implemented before live Internet ingestion goes to production.**

## Flow

```text
URL input
  → URL policy (scheme, length, blocklist)
  → DNS resolve
  → IP classification (block private, loopback, link-local, metadata)
  → HEAD request (size, content-type)
  → bounded GET (timeout, max bytes, max redirects)
  → store raw blob (UUID path)
  → safe text extraction (MIME-aware)
  → sanitize for prompt injection patterns
  → SourceSnapshot record
```

## Controls

| Threat | Control |
|---|---|
| SSRF | IP allowlist after DNS; block RFC1918, loopback, metadata IPs |
| DNS rebinding | Pin resolved IP for connection duration |
| Redirect abuse | Re-validate each hop; max redirects |
| Oversized download | Content-Length + streaming byte cap |
| Decompression bomb | Max uncompressed ratio / bytes |
| MIME spoof | Magic bytes + allowlist |
| Prompt injection | DATA blocks; never execute retrieved instructions |

## Implementation location

`libs/security/fetch/` (Phase 4)

## Content rule

> Retrieved content is DATA, never trusted instruction.
