"""Capability-routed content acquisition with honest failure taxonomy."""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from enum import StrEnum
from urllib.parse import urlparse

from deepscout_research.fetch.secure import SecureFetchError, secure_fetch
from deepscout_research.source_fabric.normalizers import (
    NormalizedContent,
    normalize_fetch_result,
)
from deepscout_research.source_fabric.registry import ConnectorRegistry
from deepscout_research.source_fabric.strategy import infer_source_kind


class SourceAccessFailure(StrEnum):
    DISCOVERED_BUT_UNFETCHABLE = "discovered_but_unfetchable"
    AUTH_REQUIRED = "auth_required"
    RATE_LIMITED = "rate_limited"
    REMOVED = "removed"
    UNSUPPORTED_CONTENT = "unsupported_content"
    PAYWALLED = "paywalled"
    BLOCKED = "blocked"
    PARSER_FAILURE = "parser_failure"


class ContentAcquisitionError(RuntimeError):
    def __init__(self, reason: SourceAccessFailure, detail: str = "") -> None:
        super().__init__(detail or reason.value)
        self.reason = reason


def classify_fetch_failure(exc: Exception) -> SourceAccessFailure:
    lowered = str(exc).casefold()
    if any(item in lowered for item in ("http 401", "http 403", "authentication")):
        return SourceAccessFailure.AUTH_REQUIRED
    if "http 429" in lowered or "rate limit" in lowered:
        return SourceAccessFailure.RATE_LIMITED
    if any(item in lowered for item in ("http 404", "http 410", "removed")):
        return SourceAccessFailure.REMOVED
    if any(item in lowered for item in ("blocked", "private", "metadata ip")):
        return SourceAccessFailure.BLOCKED
    if any(item in lowered for item in ("paywall", "payment required", "http 402")):
        return SourceAccessFailure.PAYWALLED
    if isinstance(exc, (ValueError, ET.ParseError, json.JSONDecodeError)):
        return SourceAccessFailure.PARSER_FAILURE
    return SourceAccessFailure.DISCOVERED_BUT_UNFETCHABLE


def _extract_json_object(text: str, marker: str) -> dict:
    start = text.find(marker)
    if start < 0:
        return {}
    brace = text.find("{", start + len(marker))
    if brace < 0:
        return {}
    depth = 0
    quoted = False
    escaped = False
    for index in range(brace, min(len(text), brace + 1_500_000)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(text[brace : index + 1])
                except json.JSONDecodeError:
                    return {}
                return value if isinstance(value, dict) else {}
    return {}


def _youtube_content(url: str) -> NormalizedContent:
    page = secure_fetch(url, max_bytes=2_000_000)
    raw = page.body.decode("utf-8", errors="replace")
    player = _extract_json_object(raw, "ytInitialPlayerResponse")
    details = player.get("videoDetails") or {}
    microformat = (player.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    title = str(details.get("title") or microformat.get("title") or "")
    creator = str(details.get("author") or microformat.get("ownerChannelName") or "")
    description = str(details.get("shortDescription") or microformat.get("description") or "")
    publish_date = str(microformat.get("publishDate") or microformat.get("uploadDate") or "")
    captions = player.get("captions") or {}
    tracklist = captions.get("playerCaptionsTracklistRenderer") or {}
    tracks = tracklist.get("captionTracks") or []
    transcript_lines: list[str] = []
    transcript_url = ""
    caption_language = ""
    caption_representation = "none"
    if tracks:
        # The platform orders its native caption tracks. Do not silently replace
        # original-language speech with an English translated track.
        selected = tracks[0]
        caption_language = str(selected.get("languageCode") or "")[:32]
        caption_representation = (
            "platform_auto_caption"
            if str(selected.get("kind") or "").casefold() == "asr"
            else "platform_caption"
        )
        transcript_url = str(selected.get("baseUrl") or "")
        if transcript_url:
            transcript = secure_fetch(transcript_url, max_bytes=2_000_000)
            try:
                transcript_lower = transcript.body.lower()
                if b"<!doctype" in transcript_lower or b"<!entity" in transcript_lower:
                    raise ET.ParseError("xml_doctype_or_entity_not_allowed")
                root = ET.fromstring(transcript.body)
                for node in root.iter("text"):
                    start = float(node.attrib.get("start", "0") or 0)
                    minutes, seconds = divmod(int(start), 60)
                    hours, minutes = divmod(minutes, 60)
                    stamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    value = re.sub(r"\s+", " ", html.unescape("".join(node.itertext()))).strip()
                    if value:
                        transcript_lines.append(f"[{stamp}] {value}")
            except ET.ParseError:
                transcript_lines = []
    parts = [
        f"Title: {title}" if title else "",
        f"Creator: {creator}" if creator else "",
        f"Publication date: {publish_date}" if publish_date else "",
        f"Description: {description}" if description else "",
        "Transcript:",
        *transcript_lines,
    ]
    text = "\n".join(item for item in parts if item)[:500_000]
    if len(text.strip()) < 80:
        raise ContentAcquisitionError(
            SourceAccessFailure.UNSUPPORTED_CONTENT,
            "public_video_metadata_or_captions_unavailable",
        )
    return NormalizedContent(
        text=text,
        mime_type="text/plain",
        metadata={
            "connector": "public_video_page",
            "extraction_method": "public_metadata_and_captions",
            "creator": creator[:255],
            "publication_date": publish_date[:64],
            "transcript_available": str(bool(transcript_lines)).lower(),
            "transcript_url": transcript_url[:2000],
            "caption_language": caption_language,
            "caption_representation": caption_representation,
            "declared_language": caption_language,
            "locator_scheme": "video_timestamp" if transcript_lines else "video",
            "original_url": url,
        },
    )


class ContentAcquisitionRouter:
    def __init__(self, registry: ConnectorRegistry) -> None:
        self.registry = registry

    def acquire(self, url: str) -> NormalizedContent:
        try:
            host = (urlparse(url).hostname or "").casefold().removeprefix("www.")
            if host in {"youtube.com", "youtu.be"} or host.endswith(".youtube.com"):
                return _youtube_content(url)
            max_bytes = 8_000_000 if urlparse(url).path.endswith(".pdf") else 1_500_000
            result = secure_fetch(url, max_bytes=max_bytes)
            normalized = normalize_fetch_result(result)
            return NormalizedContent(
                text=normalized.text,
                mime_type=normalized.mime_type,
                metadata={
                    **normalized.metadata,
                    "connector": "pdf_document"
                    if "pdf" in normalized.mime_type.casefold()
                    else "secure_http",
                    "final_url": result.url,
                    "raw_bytes": str(len(result.body)),
                    "source_kind": infer_source_kind(
                        url,
                        content_type=normalized.mime_type,
                    ).value,
                },
            )
        except ContentAcquisitionError:
            raise
        except (SecureFetchError, OSError, TimeoutError, ValueError, ET.ParseError) as exc:
            raise ContentAcquisitionError(classify_fetch_failure(exc), str(exc)[:300]) from exc
