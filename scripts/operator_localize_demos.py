"""Operator-only: generate and attach IT/EN demo presentation bundles."""

# ruff: noqa: E501

from __future__ import annotations

import argparse
import json
from pathlib import Path

from deepscout_core.settings import get_settings
from deepscout_persistence.models import ResearchRunRow
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.demo.presentation import (
    load_bundled_presentation,
    merge_presentation_into_public_demo,
)
from deepscout_research.demo.presentation_catalog_it import CATALOG_IT
from sqlalchemy import select

_DATA_DIR = Path(__file__).resolve().parents[1] / "libs/research/src/deepscout_research/demo/presentation_data"


def _translate_bundle(en: dict, *, provider: str, slug: str) -> dict:
    settings = get_settings()
    if provider == "openai" and settings.openai_api_key:
        key = settings.openai_api_key.get_secret_value()
        return _translate_with_openai(en, key)
    if provider == "google" and settings.google_api_key:
        key = settings.google_api_key.get_secret_value()
        return _translate_with_gemini(en, key, slug=slug)
    raise RuntimeError("No operator translation provider configured")


def _translate_with_openai(en: dict, api_key: str) -> dict:
    import urllib.request

    prompt = f"""Translate this public demo presentation bundle from English to Italian.
Preserve markdown structure in report.body_markdown. Do not translate URLs, code, or proper nouns
that would break provenance. Return ONLY valid JSON with the same keys/structure.

{json.dumps(en, ensure_ascii=False, indent=2)}
"""
    body = json.dumps(
        {
            "model": "gpt-4.1-mini",
            "messages": [
                {"role": "system", "content": "You translate structured JSON for a research demo UI."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    text = payload["choices"][0]["message"]["content"].strip()
    return _parse_json_response(text)


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def _extract_model_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content).strip()


def _translate_text_with_gemini(text: str, api_key: str, *, context: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    model = ChatGoogleGenerativeAI(model="gemini-3.7-flash", google_api_key=api_key, temperature=0.2)
    response = model.invoke(
        [
            SystemMessage(content="Translate research demo UI text from English to Italian. Preserve markdown, URLs, and proper nouns."),
            HumanMessage(content=f"{context}\n\n{text}"),
        ]
    )
    return _extract_model_text(response.content)


def _translate_with_gemini(en: dict, api_key: str, *, slug: str) -> dict:
    catalog = CATALOG_IT.get(slug, {})
    meta = {
        "goal": catalog.get("goal") or _translate_text_with_gemini(en["goal"], api_key, context="Research goal"),
        "title": catalog.get("title")
        or _translate_text_with_gemini(en.get("title", en["goal"][:80]), api_key, context="Card title"),
        "summary": catalog.get("summary")
        or _translate_text_with_gemini(en.get("summary", ""), api_key, context="Short summary"),
        "why_interesting": catalog.get("why_interesting")
        or _translate_text_with_gemini(en.get("why_interesting", ""), api_key, context="Why interesting"),
    }
    tasks = {}
    for key, task in (en.get("tasks") or {}).items():
        tasks[key] = {
            "objective": _translate_text_with_gemini(task["objective"], api_key, context="Task objective"),
            "display_name": _translate_text_with_gemini(
                task.get("display_name", task["objective"]), api_key, context="Task label"
            ),
        }
    workers = {}
    for key, worker in (en.get("workers") or {}).items():
        workers[key] = {
            "display_name": _translate_text_with_gemini(worker.get("display_name", ""), api_key, context="Agent label"),
            "assigned_task": _translate_text_with_gemini(
                worker.get("assigned_task", ""), api_key, context="Assigned task"
            ),
        }
    report = en.get("report") or {}
    translated_report = {
        "title": _translate_text_with_gemini(report.get("title", "Research Report"), api_key, context="Report title"),
        "body_markdown": _translate_text_with_gemini(
            report.get("body_markdown", ""), api_key, context="Final research report markdown"
        ),
    }
    claims = {}
    for key, statement in (en.get("claims") or {}).items():
        claims[key] = _translate_text_with_gemini(statement, api_key, context="Research finding statement")
    return {**meta, "tasks": tasks, "workers": workers, "report": translated_report, "claims": claims}


def _attach_to_run(store: ResearchStore, row: ResearchRunRow, slug: str) -> None:
    bundled = load_bundled_presentation(slug)
    if not bundled:
        raise ValueError(f"missing presentation bundles for slug={slug}")
    snap = dict(row.config_snapshot or {})
    public_demo = dict(snap.get("public_demo") or {})
    public_demo = merge_presentation_into_public_demo({**public_demo, "slug": slug}, slug)
    store.merge_config_snapshot(row.id, {"public_demo": public_demo})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", action="append", dest="slugs")
    parser.add_argument("--translate-missing-it", action="store_true")
    parser.add_argument("--attach-db", action="store_true")
    args = parser.parse_args()

    slugs = args.slugs
    if not slugs:
        slugs = [p.name.replace(".en.json", "") for p in _DATA_DIR.glob("*.en.json")]

    for slug in slugs:
        en_path = _DATA_DIR / f"{slug}.en.json"
        it_path = _DATA_DIR / f"{slug}.it.json"
        if not en_path.exists():
            print(f"SKIP {slug}: missing {en_path.name}")
            continue
        en = json.loads(en_path.read_text(encoding="utf-8"))
        if args.translate_missing_it and not it_path.exists():
            print(f"TRANSLATE {slug} -> it")
            it = _translate_bundle(en, provider="google", slug=slug)
            it_path.write_text(json.dumps(it, ensure_ascii=False, indent=2), encoding="utf-8")
        elif not it_path.exists():
            print(f"WARN {slug}: no {it_path.name} (pass --translate-missing-it)")

    if args.attach_db:
        factory = get_session_factory()
        with factory() as session:
            store = ResearchStore(session)
            for slug in slugs:
                row = session.scalar(
                    select(ResearchRunRow).where(ResearchRunRow.public_slug == slug)
                )
                if row is None:
                    print(f"SKIP db attach {slug}: not published")
                    continue
                _attach_to_run(store, row, slug)
                print(f"ATTACHED {slug} -> {row.id}")
            store.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
