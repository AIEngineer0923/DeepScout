"""Secure fetch policy with DNS-then-connect IP pinning."""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import zlib
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse

ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]
BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata.google.internal.",
    "kubernetes.default.svc",
}


class SecureFetchError(ValueError):
    """Raised when a URL fails secure fetch policy."""


@dataclass(frozen=True, slots=True)
class FetchResult:
    url: str
    content_type: str
    body: bytes


@dataclass(frozen=True, slots=True)
class ResolvedTarget:
    url: str
    hostname: str
    port: int
    scheme: str
    path: str
    pinned_ip: ipaddress.IPv4Address | ipaddress.IPv6Address


def _strip_userinfo(parsed) -> str:
    host = parsed.hostname
    if host is None:
        raise SecureFetchError("URL must include a host")
    netloc = host.rstrip(".")
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse(
        (parsed.scheme.lower(), netloc, parsed.path or "/", parsed.params, parsed.query, "")
    )


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SecureFetchError(f"Blocked URL scheme: {parsed.scheme}")
    if not parsed.netloc:
        raise SecureFetchError("URL must include a host")
    if parsed.username or parsed.password:
        raise SecureFetchError("URL userinfo is not allowed")
    return _strip_userinfo(parsed)


def _literal_ip(hostname: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    candidate = hostname.strip("[]")
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        pass
    if candidate.isdigit():
        try:
            return ipaddress.IPv4Address(int(candidate))
        except (ValueError, OverflowError):
            return None
    return None


def _canonical_ip(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return mapped
    sixtofour = getattr(ip, "sixtofour", None)
    if sixtofour is not None:
        return sixtofour
    return ip


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    candidate = _canonical_ip(ip)
    if candidate.is_multicast or candidate.is_reserved or candidate.is_unspecified:
        return True
    return any(candidate in network for network in BLOCKED_NETWORKS)


def _resolve_host_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    literal = _literal_ip(hostname)
    if literal is not None:
        return [literal]
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SecureFetchError(f"DNS resolution failed for {hostname}") from exc
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        ips.append(ipaddress.ip_address(info[4][0]))
    if not ips:
        raise SecureFetchError(f"DNS resolution returned no addresses for {hostname}")
    return ips


def resolve_public_target(url: str) -> ResolvedTarget:
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    hostname = parsed.hostname
    if hostname is None:
        raise SecureFetchError("Missing hostname")
    host_key = hostname.lower().rstrip(".")
    if host_key in BLOCKED_HOSTS or host_key.endswith(".localhost"):
        raise SecureFetchError(f"Blocked host: {hostname}")
    ips = _resolve_host_ips(host_key)
    blocked = [ip for ip in ips if _is_blocked_ip(ip)]
    if blocked:
        raise SecureFetchError(f"Blocked private/metadata IP: {blocked[0]}")
    scheme = parsed.scheme.lower()
    port = parsed.port or (443 if scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return ResolvedTarget(
        url=normalized,
        hostname=host_key,
        port=port,
        scheme=scheme,
        path=path,
        pinned_ip=ips[0],
    )


def assert_public_target(url: str) -> str:
    return resolve_public_target(url).url


def public_http_url_or_none(url: str) -> str | None:
    try:
        return assert_public_target(url)
    except SecureFetchError:
        return None


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, hostname: str, port: int, pinned_ip: str, timeout: float):
        super().__init__(hostname, port=port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._pinned_ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        hostname: str,
        port: int,
        pinned_ip: str,
        timeout: float,
        context: ssl.SSLContext,
    ):
        super().__init__(hostname, port=port, timeout=timeout, context=context)
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        sock = socket.create_connection((self._pinned_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _read_limited(response: http.client.HTTPResponse, max_bytes: int) -> bytes:
    raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise SecureFetchError("Response exceeded byte limit")
    encoding = (response.getheader("Content-Encoding") or "").lower()
    if encoding in {"gzip", "x-gzip"}:
        try:
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
            out = decoder.decompress(raw, max_bytes + 1)
        except zlib.error as exc:
            raise SecureFetchError("Invalid compressed response") from exc
        if len(out) > max_bytes:
            raise SecureFetchError("Decompressed response exceeded byte limit")
        return out
    if encoding and encoding not in {"identity"}:
        raise SecureFetchError(f"Unsupported Content-Encoding: {encoding}")
    return raw


def _request_pinned(
    target: ResolvedTarget, *, timeout_s: float, max_bytes: int
) -> http.client.HTTPResponse:
    if target.scheme == "https":
        context = ssl.create_default_context()
        conn: http.client.HTTPConnection = _PinnedHTTPSConnection(
            target.hostname,
            target.port,
            str(target.pinned_ip),
            timeout_s,
            context,
        )
    else:
        conn = _PinnedHTTPConnection(target.hostname, target.port, str(target.pinned_ip), timeout_s)
    try:
        conn.putrequest("GET", target.path, skip_host=True, skip_accept_encoding=True)
        host = (
            target.hostname
            if target.port in {80, 443}
            else f"{target.hostname}:{target.port}"
        )
        conn.putheader("Host", host)
        conn.putheader(
            "User-Agent",
            "DeepScout/1.0 (research-bot; +https://github.com/francescoveryra-dot/deepscout)",
        )
        conn.putheader(
            "Accept",
            "text/html,application/xhtml+xml,text/plain,application/pdf;q=0.9,*/*;q=0.5",
        )
        conn.putheader("Accept-Encoding", "identity")
        conn.putheader("Connection", "close")
        conn.endheaders()
        return conn.getresponse()
    except (OSError, ssl.SSLError, TimeoutError, http.client.HTTPException) as exc:
        conn.close()
        raise SecureFetchError(f"Fetch failed: {exc}") from exc


def secure_fetch(
    url: str,
    *,
    timeout_s: float = 10.0,
    max_bytes: int = 1_000_000,
) -> FetchResult:
    """Fetch a public URL after resolving DNS and pinning the TCP connect to that IP.

    Redirects are re-resolved and re-pinned hop by hop. TLS still verifies the
    original hostname (SNI + certificate), not the numeric IP.
    """
    current = url
    for _ in range(5):
        target = resolve_public_target(current)
        response = _request_pinned(target, timeout_s=timeout_s, max_bytes=max_bytes)
        try:
            if 300 <= response.status < 400:
                location = response.getheader("Location")
                if not location:
                    raise SecureFetchError("Redirect without location header")
                current = urljoin(target.url, location)
                continue
            if response.status >= 400:
                raise SecureFetchError(f"Upstream returned HTTP {response.status}")
            content_type = response.getheader("Content-Type") or "application/octet-stream"
            body = _read_limited(response, max_bytes)
            return FetchResult(url=target.url, content_type=content_type, body=body)
        finally:
            response.close()
    raise SecureFetchError("Too many redirects")
