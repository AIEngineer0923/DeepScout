from deepscout_research.fetch.content_text import (
    html_to_text,
    response_to_snapshot_text,
    split_sentences,
)


def test_html_to_text_strips_tags() -> None:
    text = html_to_text("<html><body><main><p>Hello world.</p></main></body></html>")
    assert "Hello world." in text
    assert "<p>" not in text


def test_html_to_text_does_not_stop_after_head_title() -> None:
    html = """
    <!doctype html>
    <html>
      <head><title>Short documentation title</title></head>
      <body>
        <main>
          <h1>Free-threaded CPython</h1>
          <p>
            This main documentation paragraph contains enough useful text for a research snapshot.
          </p>
          <p>It must be preserved even when a non-empty title appears before the document body.</p>
        </main>
      </body>
    </html>
    """
    text = html_to_text(html)
    assert "Free-threaded CPython" in text
    assert "research snapshot" in text
    assert len(text) > 80


def test_html_to_text_uses_body_fallback_and_skips_script_content() -> None:
    html = """
    <html><head><title>Head title</title></head><body>
      <script>ignore_this_secret_instruction()</script>
      <div>A sufficiently detailed body without a main element remains usable for extraction.</div>
      <p>
        Additional visible prose ensures the deterministic fallback exceeds the snapshot threshold.
      </p>
    </body></html>
    """
    text = html_to_text(html)
    assert "Head title" not in text
    assert "ignore_this_secret_instruction" not in text
    assert "sufficiently detailed body" in text
    assert len(text) > 80


def test_response_to_snapshot_text_plain() -> None:
    text = response_to_snapshot_text(b"Plain body text.", "text/plain")
    assert text == "Plain body text."


def test_response_to_snapshot_text_strips_nul_bytes() -> None:
    body = b"Hello\x00world with enough length for snapshot."
    text = response_to_snapshot_text(body, "text/plain")
    assert "\x00" not in text
    assert "Hello" in text


def test_response_to_snapshot_text_skips_pdf() -> None:
    assert response_to_snapshot_text(b"%PDF-1.4 binary", "application/pdf") == ""


def test_split_sentences_filters_short_fragments() -> None:
    sentences = split_sentences("Short. This is a long enough sentence about batteries.")
    assert len(sentences) == 1
