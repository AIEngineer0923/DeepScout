from deepscout_research.fetch.url_normalize import normalize_source_url


def test_normalize_source_url_strips_www_and_trailing_slash() -> None:
    assert normalize_source_url("https://www.Example.com/path/") == normalize_source_url(
        "https://example.com/path"
    )
