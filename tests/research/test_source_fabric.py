from __future__ import annotations

import io
import json
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
import pytest
from deepscout_core.domain.contracts import SourceKind
from deepscout_core.domain.schemas import SearchResult
from deepscout_research.contracts.source_portfolio import SourcePortfolioTracker, source_family
from deepscout_research.fetch.secure import FetchResult
from deepscout_research.source_fabric.acquisition import _youtube_content
from deepscout_research.source_fabric.normalizers import (
    normalize_fetch_result,
    normalize_pdf,
)
from deepscout_research.source_fabric.providers import _bounded_json
from deepscout_research.source_fabric.registry import (
    SourceCapability,
    baseline_connector_registry,
)
from deepscout_research.source_fabric.router import DiscoveryRouter
from deepscout_research.source_fabric.strategy import (
    DiscoveryRequest,
    infer_source_kind,
    plan_source_strategy,
)
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def test_baseline_registry_describes_real_optional_paths() -> None:
    registry = baseline_connector_registry()
    assert registry.get("indexed_web").discovery_supported is True  # type: ignore[union-attr]
    assert registry.get("openalex").authentication_required is False  # type: ignore[union-attr]
    assert registry.get("github_public_api").structured_data_supported is True  # type: ignore[union-attr]
    video = registry.get("public_video_page")
    assert video is not None and video.transcript_supported is True
    assert "captions are unavailable" in " ".join(video.known_restrictions)


def test_source_kind_is_separate_from_authority_and_extensible() -> None:
    assert infer_source_kind("https://youtu.be/abc") == SourceKind.VIDEO
    assert infer_source_kind("https://github.com/org/repo") == SourceKind.REPOSITORY
    assert infer_source_kind("https://example.org/report.pdf") == SourceKind.DOCUMENT
    assert (
        infer_source_kind("https://reddit.com/r/test/comments/1") == SourceKind.COMMUNITY_DISCUSSION
    )


def test_strategy_scales_portfolio_by_mode_and_objective() -> None:
    objective = "Compare scientific studies and GitHub documentation with a useful video tutorial"
    quick = plan_source_strategy(objective, None, research_mode="quick")
    deep = plan_source_strategy(objective, None, research_mode="deep")
    assert SourceKind.ACADEMIC_PAPER in deep.requested_kinds
    assert SourceKind.REPOSITORY in deep.requested_kinds
    assert SourceKind.VIDEO in deep.requested_kinds
    assert deep.target_independent_publishers > quick.target_independent_publishers
    assert deep.minimum_query_families > quick.minimum_query_families


class _Provider:
    def __init__(self, name: str, kinds: set[SourceKind], results=None, error=None) -> None:
        self.provider_name = name
        self.capability = SourceCapability(
            connector_id=name,
            source_kinds=frozenset(kinds),
            discovery_supported=True,
        )
        self.results = results or []
        self.error = error

    def discover(self, request: DiscoveryRequest) -> list[SearchResult]:
        del request
        if self.error:
            raise self.error
        return self.results

    def close(self) -> None:
        return None


def test_router_falls_back_and_deduplicates_provider_results() -> None:
    url = "https://doi.org/10.1000/example"
    failed = _Provider("indexed_web", {SourceKind.ACADEMIC_PAPER}, error=TimeoutError())
    academic = _Provider(
        "openalex",
        {SourceKind.ACADEMIC_PAPER},
        results=[
            SearchResult(url=url, title="Paper", discovery_provider="openalex"),
            SearchResult(url=url + "#fragment", title="Duplicate"),
        ],
    )
    router = DiscoveryRouter([failed, academic], baseline_connector_registry())
    results = router.discover(
        DiscoveryRequest(
            query="test",
            source_kinds=frozenset({SourceKind.ACADEMIC_PAPER}),
        )
    )
    assert [item.url for item in results] == [url]
    assert [item.success for item in router.last_attempts] == [False, True]


def test_portfolio_requires_multiple_query_families_for_standard() -> None:
    strategy = plan_source_strategy("product comparison", None, research_mode="standard")
    tracker = SourcePortfolioTracker(strategy)
    for index in range(3):
        tracker.admit(SearchResult(url=f"https://publisher{index}.example/article"))
    tracker.finish_query(3)
    assert tracker.adequate() is False
    tracker.finish_query(0)
    assert tracker.adequate() is True
    assert source_family("https://a.news.example.co.uk/story") == "example.co.uk"


def test_json_and_feed_normalization_preserve_structured_content() -> None:
    json_result = normalize_fetch_result(
        FetchResult(
            url="https://data.example/api",
            content_type="application/json",
            body=json.dumps({"series": [{"year": 2026, "value": 42}]}).encode(),
        )
    )
    assert "series[0].year: 2026" in json_result.text
    feed_result = normalize_fetch_result(
        FetchResult(
            url="https://news.example/feed.xml",
            content_type="application/rss+xml",
            body=(
                b"<rss><channel><item><title>Update</title>"
                b"<pubDate>2026-08-24</pubDate><author>Evidence Desk</author>"
                b"</item></channel></rss>"
            ),
        )
    )
    assert "title: Update" in feed_result.text
    assert feed_result.metadata["feed_or_xml"] == "true"
    assert feed_result.metadata["publication_date"] == "2026-08-24"
    assert feed_result.metadata["creator"] == "Evidence Desk"

    html_result = normalize_fetch_result(
        FetchResult(
            url="https://news.example/article",
            content_type="text/html",
            body=(
                b'<html><head><meta property="article:published_time" content="2026-08-24">'
                b'<meta name="author" content="Research Desk">'
                b'<meta property="og:site_name" content="Evidence News"></head>'
                b"<body>Measured public evidence in the original article.</body></html>"
            ),
        )
    )
    assert html_result.metadata["publication_date"] == "2026-08-24"
    assert html_result.metadata["creator"] == "Research Desk"
    assert html_result.metadata["publisher"] == "Evidence News"


def test_xml_entities_and_oversized_structured_responses_are_rejected() -> None:
    hostile_xml = b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><x>&secret;</x>'
    with pytest.raises(ValueError, match="DOCTYPE|entity"):
        normalize_fetch_result(
            FetchResult(
                url="https://data.example/feed.xml",
                content_type="application/xml",
                body=hostile_xml,
            )
        )

    response = httpx.Response(
        200,
        headers={"content-length": str(3 * 1024 * 1024)},
        content=b"{}",
    )
    with pytest.raises(ValueError, match="size limit"):
        _bounded_json(response)


def test_pdf_normalizer_extracts_text_with_page_locator() -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)  # noqa: SLF001 - deterministic test fixture
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (DeepScout PDF evidence) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)  # noqa: SLF001
    output = io.BytesIO()
    writer.write(output)
    normalized = normalize_pdf(output.getvalue())
    assert "[Page 1]" in normalized.text
    assert "DeepScout PDF evidence" in normalized.text
    assert normalized.metadata["locator_scheme"] == "page"


def test_public_youtube_path_preserves_timestamp_or_honest_metadata() -> None:
    player = {
        "videoDetails": {
            "title": "Research update",
            "author": "Evidence Lab",
            "shortDescription": "A public evidence briefing.",
        },
        "microformat": {"playerMicroformatRenderer": {"publishDate": "2026-08-24"}},
        "captions": {
            "playerCaptionsTracklistRenderer": {
                "captionTracks": [
                    {"languageCode": "en", "baseUrl": "https://www.youtube.com/api/timedtext?v=x"}
                ]
            }
        },
    }
    page = f"<script>var ytInitialPlayerResponse = {json.dumps(player)};</script>".encode()
    transcript = b'<transcript><text start="83.2" dur="2">Measured result</text></transcript>'
    with patch(
        "deepscout_research.source_fabric.acquisition.secure_fetch",
        side_effect=[
            FetchResult("https://youtube.com/watch?v=x", "text/html", page),
            FetchResult("https://youtube.com/api/timedtext?v=x", "text/xml", transcript),
        ],
    ):
        normalized = _youtube_content("https://youtube.com/watch?v=x")
    assert "[00:01:23] Measured result" in normalized.text
    assert normalized.metadata["transcript_available"] == "true"
    original_url = urlsplit(normalized.metadata["original_url"])
    assert original_url.scheme == "https"
    assert original_url.hostname == "youtube.com"
