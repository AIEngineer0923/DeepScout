"""SSRF policy tests including encodings, userinfo, and pinning helpers."""

from unittest.mock import patch

import pytest
from deepscout_research.fetch.secure import (
    SecureFetchError,
    assert_public_target,
    normalize_url,
    resolve_public_target,
)


def test_blocks_file_scheme() -> None:
    with pytest.raises(SecureFetchError):
        normalize_url("file:///etc/passwd")


def test_blocks_userinfo() -> None:
    with pytest.raises(SecureFetchError):
        normalize_url("https://user:pass@example.com/")


def test_blocks_localhost() -> None:
    with pytest.raises(SecureFetchError):
        assert_public_target("http://localhost/test")


def test_blocks_trailing_dot_localhost() -> None:
    with pytest.raises(SecureFetchError):
        assert_public_target("http://localhost./test")


def test_blocks_ipv4_loopback_literal() -> None:
    with pytest.raises(SecureFetchError):
        assert_public_target("http://127.0.0.1/secret")


def test_blocks_ipv6_loopback_literal() -> None:
    with pytest.raises(SecureFetchError):
        assert_public_target("http://[::1]/secret")


def test_blocks_rfc1918() -> None:
    with pytest.raises(SecureFetchError):
        assert_public_target("http://10.0.0.8/internal")


def test_blocks_link_local_and_metadata() -> None:
    with pytest.raises(SecureFetchError):
        assert_public_target("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(SecureFetchError):
        assert_public_target("http://metadata.google.internal/")


def test_blocks_decimal_loopback() -> None:
    with pytest.raises(SecureFetchError):
        assert_public_target("http://2130706433/")


def test_blocks_ipv4_mapped_loopback() -> None:
    with pytest.raises(SecureFetchError):
        assert_public_target("http://[::ffff:127.0.0.1]/")


def test_blocks_cgnat() -> None:
    with pytest.raises(SecureFetchError):
        assert_public_target("http://100.64.0.1/")


def test_allows_public_https() -> None:
    url = assert_public_target("https://example.com/article")
    assert url.startswith("https://example.com")


def test_resolve_pins_resolved_ip() -> None:
    fake_ip = "93.184.216.34"
    with patch(
        "deepscout_research.fetch.secure.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", (fake_ip, 0))],
    ):
        target = resolve_public_target("https://example.com/path")
    assert str(target.pinned_ip) == fake_ip
    assert target.hostname == "example.com"


def test_dns_rebinding_blocked_if_any_private_record() -> None:
    with patch(
        "deepscout_research.fetch.secure.socket.getaddrinfo",
        return_value=[
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("127.0.0.1", 0)),
        ],
    ):
        with pytest.raises(SecureFetchError):
            resolve_public_target("https://rebinder.example/")
