"""Public demo presentation overlays — precomputed, read-only at browse time."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LOCALES = frozenset({"en", "it"})
_DATA_DIR = Path(__file__).parent / "presentation_data"


def normalize_locale(locale: str | None) -> str:
    if not locale:
        return "en"
    value = locale.strip().lower()[:2]
    return value if value in LOCALES else "en"


def load_bundled_presentation(slug: str) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for loc in ("en", "it"):
        path = _DATA_DIR / f"{slug}.{loc}.json"
        if path.exists():
            merged[loc] = json.loads(path.read_text(encoding="utf-8"))
    return merged


def resolve_presentation(
    snapshot: dict[str, Any] | None,
    slug: str | None,
    locale: str,
) -> dict[str, Any] | None:
    """Return locale-specific presentation dict from DB snapshot or bundled files."""
    loc = normalize_locale(locale)
    public = (snapshot or {}).get("public_demo") or {}
    stored = (public.get("presentation") or {}).get(loc)
    if stored:
        return stored
    if slug:
        bundled = load_bundled_presentation(slug)
        if loc in bundled:
            return bundled[loc]
        if "en" in bundled:
            return bundled["en"]
    return None


def merge_presentation_into_public_demo(
    public_demo: dict[str, Any],
    slug: str,
    *,
    bundled_only: bool = False,
) -> dict[str, Any]:
    """Attach bundled EN/IT presentation to public_demo metadata for publication."""
    bundled = load_bundled_presentation(slug)
    if not bundled:
        return public_demo
    presentation = dict(public_demo.get("presentation") or {})
    for loc, data in bundled.items():
        presentation.setdefault(loc, data)
    public_demo = dict(public_demo)
    public_demo["presentation"] = presentation
    if bundled_only:
        return public_demo
    en = bundled.get("en") or {}
    public_demo.setdefault("title", en.get("title"))
    public_demo.setdefault("summary", en.get("summary"))
    public_demo.setdefault("why_interesting", en.get("why_interesting"))
    return public_demo


def _clean_presentation_text(value: str) -> str:
    text = value.strip()
    for prefix in (
        "Obiettivo dell'attività\n\n",
        "Obiettivo del task\n\n",
        "Etichetta attività\n\n",
        "Etichetta agente\n\n",
        "Compito assegnato\n\n",
        "Attività assegnata\n\n",
        "Titolo della scheda\n\n",
        "Breve sintesi\n\n",
        "Perché è interessante\n\n",
        "Obiettivo della ricerca\n\n",
    ):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.strip()


def build_presentation_payload(
    workspace: dict[str, Any],
    presentation: dict[str, Any] | None,
    *,
    locale: str,
) -> dict[str, Any] | None:
    """Shape localized presentation for API consumers without mutating authoritative fields."""
    if not presentation:
        return None

    tasks: dict[str, dict[str, str]] = {}
    pres_tasks = presentation.get("tasks") or {}
    for task in workspace.get("tasks") or []:
        key = task.get("task_key") or task.get("id")
        overlay = pres_tasks.get(key) or pres_tasks.get(task.get("id", "")) or {}
        objective = overlay.get("objective") or task.get("objective", "")
        display_name = overlay.get("display_name") or task.get("display_name", "")
        tasks[key] = {
            "objective": _clean_presentation_text(objective),
            "display_name": _clean_presentation_text(display_name),
            "rationale": _clean_presentation_text(overlay.get("rationale", "")),
        }

    workers: dict[str, dict[str, str]] = {}
    pres_workers = presentation.get("workers") or {}
    for worker in workspace.get("workers") or []:
        wid = worker.get("worker_id", "")
        overlay = pres_workers.get(wid) or {}
        worker_name = overlay.get("display_name") or worker.get("display_name", "")
        assigned_task = overlay.get("assigned_task") or worker.get("assigned_task", "")
        workers[wid] = {
            "display_name": _clean_presentation_text(worker_name),
            "assigned_task": _clean_presentation_text(assigned_task),
        }

    claims: dict[str, dict[str, str]] = {}
    pres_claims = presentation.get("claims") or {}
    for claim in workspace.get("claims") or []:
        cid = claim.get("id", "")
        statement = (
            pres_claims.get(cid)
            or pres_claims.get(claim.get("statement", ""))
            or claim.get("statement", "")
        )
        claims[cid] = {"statement": statement}

    report = None
    pres_report = presentation.get("report") or {}
    authoritative = workspace.get("report")
    if pres_report.get("body_markdown") or pres_report.get("title"):
        auth = authoritative or {}
        report = {
            "title": pres_report.get("title") or auth.get("title", "Research Report"),
            "body_markdown": pres_report.get("body_markdown") or auth.get("body_markdown", ""),
            "is_localized": bool(pres_report.get("body_markdown")),
        }
    elif authoritative:
        report = {
            "title": authoritative.get("title", "Research Report"),
            "body_markdown": authoritative.get("body_markdown", ""),
            "is_localized": False,
        }

    title_source = presentation.get("title") or presentation.get("goal", "")[:120]
    return {
        "locale": normalize_locale(locale),
        "goal": _clean_presentation_text(presentation.get("goal") or workspace.get("goal", "")),
        "title": _clean_presentation_text(title_source),
        "summary": _clean_presentation_text(presentation.get("summary", "")),
        "why_interesting": _clean_presentation_text(presentation.get("why_interesting", "")),
        "quality_intro": _clean_presentation_text(presentation.get("quality_intro", "")),
        "tasks": tasks,
        "workers": workers,
        "claims": claims,
        "report": report,
    }


def localized_demo_card_fields(
    meta: dict[str, Any],
    presentation: dict[str, Any] | None,
) -> dict[str, str | None]:
    if not presentation:
        return {
            "demo_title": meta.get("title"),
            "demo_summary": meta.get("summary"),
            "demo_why": meta.get("why_interesting"),
            "demo_goal": meta.get("goal"),
        }
    return {
        "demo_title": presentation.get("title") or meta.get("title"),
        "demo_summary": presentation.get("summary") or meta.get("summary"),
        "demo_why": presentation.get("why_interesting") or meta.get("why_interesting"),
        "demo_goal": presentation.get("goal"),
    }
