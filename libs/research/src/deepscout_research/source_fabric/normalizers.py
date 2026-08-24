"""Bounded content normalizers preserving document-level provenance."""

from __future__ import annotations

import io
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

from pypdf import PdfReader

from deepscout_research.fetch.content_text import html_to_text, normalize_plain_text
from deepscout_research.fetch.secure import FetchResult


@dataclass(frozen=True, slots=True)
class NormalizedContent:
    text: str
    mime_type: str
    metadata: dict[str, str] = field(default_factory=dict)


class _DocumentMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metadata: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "meta":
            return
        values = {key.casefold(): value or "" for key, value in attrs}
        key = (values.get("property") or values.get("name") or values.get("itemprop")).casefold()
        content = values.get("content", "").strip()[:2000]
        if not content:
            return
        if key in {
            "article:published_time",
            "og:published_time",
            "date",
            "datepublished",
            "publication_date",
        }:
            self.metadata.setdefault("publication_date", content[:64])
        elif key in {"author", "article:author", "creator"}:
            self.metadata.setdefault("creator", content[:255])
        elif key in {"og:site_name", "publisher", "application-name"}:
            self.metadata.setdefault("publisher", content[:255])


def _html_metadata(raw: str) -> dict[str, str]:
    parser = _DocumentMetadataParser()
    try:
        parser.feed(raw[:1_500_000])
    except Exception:
        return {}
    return parser.metadata


def _xml_metadata(body: bytes) -> dict[str, str]:
    root = ET.fromstring(body)
    metadata: dict[str, str] = {}
    for element in list(root.iter())[:500]:
        tag = _tag_name(element.tag).casefold()
        value = normalize_plain_text(element.text or "")
        if not value:
            continue
        if tag in {"pubdate", "published", "updated", "date"}:
            metadata.setdefault("publication_date", value[:64])
        elif tag in {"author", "creator"}:
            metadata.setdefault("creator", value[:255])
    return metadata


def _json_lines(value: Any, *, prefix: str = "", depth: int = 0) -> list[str]:
    if depth > 8:
        return []
    if isinstance(value, dict):
        lines: list[str] = []
        for key, child in list(value.items())[:500]:
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_json_lines(child, prefix=next_prefix, depth=depth + 1))
        return lines
    if isinstance(value, list):
        lines = []
        for index, child in enumerate(value[:500]):
            lines.extend(_json_lines(child, prefix=f"{prefix}[{index}]", depth=depth + 1))
        return lines
    if value is None:
        return []
    return [f"{prefix}: {value}"[:4000]]


def normalize_json(body: bytes) -> str:
    payload = json.loads(body.decode("utf-8", errors="strict"))
    return normalize_plain_text("\n".join(_json_lines(payload)))[:500_000]


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalize_xml(body: bytes) -> str:
    lowered_body = body.lower()
    if b"<!doctype" in lowered_body or b"<!entity" in lowered_body:
        raise ValueError("xml_doctype_or_entity_not_allowed")
    root = ET.fromstring(body)
    lines: list[str] = []
    for element in root.iter():
        text = normalize_plain_text(element.text or "")
        if text:
            lines.append(f"{_tag_name(element.tag)}: {text}")
        if len(lines) >= 10_000:
            break
    return "\n".join(lines)[:500_000]


def normalize_pdf(body: bytes) -> NormalizedContent:
    reader = PdfReader(io.BytesIO(body), strict=False)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("encrypted_pdf") from exc
    parts: list[str] = []
    for page_number, page in enumerate(reader.pages[:300], start=1):
        extracted = normalize_plain_text(page.extract_text() or "")
        if extracted:
            parts.append(f"[Page {page_number}] {extracted}")
        if sum(len(item) for item in parts) >= 500_000:
            break
    text = "\n".join(parts)[:500_000]
    return NormalizedContent(
        text=text,
        mime_type="application/pdf",
        metadata={
            "extraction_method": "pypdf_text",
            "page_count": str(len(reader.pages)),
            "locator_scheme": "page",
        },
    )


def normalize_fetch_result(result: FetchResult) -> NormalizedContent:
    lowered = result.content_type.casefold()
    stripped = result.body.lstrip()
    if "pdf" in lowered or stripped.startswith(b"%PDF-"):
        return normalize_pdf(result.body)
    if "json" in lowered or stripped.startswith((b"{", b"[")):
        return NormalizedContent(
            text=normalize_json(result.body),
            mime_type=result.content_type,
            metadata={"extraction_method": "bounded_json_tree"},
        )
    if any(item in lowered for item in ("xml", "rss", "atom")) or stripped.startswith(b"<?xml"):
        return NormalizedContent(
            text=normalize_xml(result.body),
            mime_type=result.content_type,
            metadata={
                "extraction_method": "bounded_xml_tree",
                "feed_or_xml": "true",
                **_xml_metadata(result.body),
            },
        )
    charset = "utf-8"
    match = re.search(r"charset=([^;\s]+)", lowered)
    if match:
        charset = match.group(1).strip("\"'")
    raw = result.body.decode(charset, errors="replace")
    if "html" in lowered or stripped[:20].casefold().startswith((b"<!doctype", b"<html")):
        return NormalizedContent(
            text=html_to_text(raw)[:500_000],
            mime_type=result.content_type,
            metadata={
                "extraction_method": "deterministic_visible_text",
                **_html_metadata(raw),
            },
        )
    return NormalizedContent(
        text=normalize_plain_text(raw)[:500_000],
        mime_type=result.content_type,
        metadata={"extraction_method": "bounded_plain_text"},
    )
