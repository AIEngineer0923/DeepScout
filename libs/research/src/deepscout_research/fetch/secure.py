"""Secure fetch policy and client foundation."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class SecureFetchError(ValueError):
    """Raised when a URL fails secure fetch policy."""


@dataclass(frozen=True, slots=True)
class FetchResult:
    url: str
    content_type: str
    body: bytes


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SecureFetchError(f"Blocked URL scheme: {parsed.scheme}")
    if not parsed.netloc:
        raise SecureFetchError("URL must include a host")
    return parsed.geturl()


def _resolve_host_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SecureFetchError(f"DNS resolution failed for {hostname}") from exc
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        ips.append(ip)
    return ips


def assert_public_target(url: str) -> str:
    normalized = normalize_url(url)
    hostname = urlparse(normalized).hostname
    if hostname is None:
        raise SecureFetchError("Missing hostname")
    if hostname.lower() in {"localhost", "metadata.google.internal"}:
        raise SecureFetchError(f"Blocked host: {hostname}")
    for ip in _resolve_host_ips(hostname):
        for network in BLOCKED_NETWORKS:
            if ip in network:
                raise SecureFetchError(f"Blocked private/metadata IP: {ip}")
    return normalized


def secure_fetch(
    url: str,
    *,
    timeout_s: float = 10.0,
    max_bytes: int = 1_000_000,
) -> FetchResult:
    """Fetch a public URL with basic SSRF controls.

    Limitation: DNS rebinding between resolve and connect is not fully pinned
    in this httpx-based implementation; production hardening may require a
    custom transport with connection-level IP pinning.
    """
    safe_url = assert_public_target(url)
    with httpx.Client(
        follow_redirects=False,
        timeout=timeout_s,
        headers={
            "User-Agent": "DeepScout/1.0 (research-bot; +https://github.com/francescoveryra-dot/deepscout)"
        },
    ) as client:
        current = safe_url
        for _ in range(5):
            response = client.get(current)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise SecureFetchError("Redirect without location header")
                current = assert_public_target(location)
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "application/octet-stream")
            body = response.content[:max_bytes]
            return FetchResult(url=current, content_type=content_type, body=body)
    raise SecureFetchError("Too many redirects")
