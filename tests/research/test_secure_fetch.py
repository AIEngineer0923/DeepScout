import pytest
from deepscout_research.fetch.secure import SecureFetchError, assert_public_target, normalize_url


def test_blocks_file_scheme() -> None:
    with pytest.raises(SecureFetchError):
        normalize_url("file:///etc/passwd")


def test_blocks_localhost() -> None:
    with pytest.raises(SecureFetchError):
        assert_public_target("http://localhost/test")


def test_allows_public_https() -> None:
    url = assert_public_target("https://example.com/article")
    assert url.startswith("https://example.com")
