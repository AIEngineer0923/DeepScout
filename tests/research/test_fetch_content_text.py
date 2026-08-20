from deepscout_research.fetch.content_text import (
    html_to_text,
    response_to_snapshot_text,
    split_sentences,
)


def test_html_to_text_strips_tags() -> None:
    text = html_to_text("<html><body><main><p>Hello world.</p></main></body></html>")
    assert "Hello world." in text
    assert "<p>" not in text


def test_response_to_snapshot_text_plain() -> None:
    text = response_to_snapshot_text(b"Plain body text.", "text/plain")
    assert text == "Plain body text."


def test_split_sentences_filters_short_fragments() -> None:
    sentences = split_sentences("Short. This is a long enough sentence about batteries.")
    assert len(sentences) == 1
