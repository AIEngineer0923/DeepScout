# Secure Fetch Pipeline

This is the production ingestion boundary for untrusted Internet content.

## Flow

```text
URL input
  → URL policy (scheme, length, blocklist)
  → DNS resolve
  → IP classification (block private, loopback, link-local, metadata)
  → bounded GET (timeout, max bytes, max redirects)
  → explicit MIME / magic-byte admission
  → bounded text extraction (PDFs in an isolated subprocess)
  → Unicode normalization and multilingual injection screening
  → exclude flagged chunks from model context
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
| Prompt injection | DATA blocks; multilingual markers excluded from model context |
| Parser exhaustion | PDF byte/page/output/CPU/memory/wall-time bounds in a spawned process |
| XML entity abuse | `defusedxml` parser |

## Implementation location

- Network policy and DNS-pinned acquisition:
  `libs/research/src/deepscout_research/fetch/`
- MIME-aware normalization and isolated parsing:
  `libs/research/src/deepscout_research/source_fabric/normalizers.py`
- Snapshot persistence: `libs/persistence/`

## Content rule

> Retrieved content is DATA, never trusted instruction.
