"""Fail-closed validation for public demo presentation bundles."""

from __future__ import annotations

from typing import Any
from uuid import UUID

PRESENTATION_VERSION = 1
SUPPORTED_PRESENTATION_VERSIONS = frozenset({1})
REQUIRED_LOCALES = ("en", "it")
REQUIRED_STRING_FIELDS = ("goal", "title", "summary", "why_interesting")
MIN_TEXT_LEN = 8
MIN_REPORT_LEN = 80


class PresentationValidationError(ValueError):
    """Raised when a presentation bundle fails publication validation."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(self.detail)


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", f"{field} must be a string")
    text = value.strip()
    if len(text) < MIN_TEXT_LEN:
        raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", f"{field} is empty or too short")
    return text


def validate_presentation_bundle(
    bundle: Any,
    *,
    locale: str,
    run_task_keys: set[str],
    run_worker_ids: set[str],
    run_claim_ids: set[str],
    expected_run_id: UUID | None = None,
) -> None:
    """Validate one locale bundle. Raises PresentationValidationError on failure."""
    if locale not in REQUIRED_LOCALES:
        raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", f"unsupported locale {locale}")

    if not isinstance(bundle, dict):
        raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", "bundle must be an object")

    bundle_run_id = bundle.get("run_id")
    if bundle_run_id is not None and expected_run_id is not None:
        if str(bundle_run_id) != str(expected_run_id):
            raise PresentationValidationError(
                "PRESENTATION_SCHEMA_INVALID",
                "bundle run_id does not match publication run",
            )

    version = bundle.get("version", PRESENTATION_VERSION)
    if not isinstance(version, int):
        raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", "version must be an integer")
    if version not in SUPPORTED_PRESENTATION_VERSIONS:
        raise PresentationValidationError("PRESENTATION_VERSION_UNSUPPORTED", f"unsupported version {version}")

    bundle_locale = bundle.get("locale")
    if bundle_locale is not None and str(bundle_locale).lower()[:2] != locale:
        raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", "bundle locale mismatch")

    for field in REQUIRED_STRING_FIELDS:
        _require_non_empty_string(bundle.get(field), field=field)

    report = bundle.get("report")
    if not isinstance(report, dict):
        raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", "report must be an object")
    report_body = _require_non_empty_string(report.get("body_markdown"), field="report.body_markdown")
    if len(report_body) < MIN_REPORT_LEN:
        raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", "report.body_markdown is too short")

    tasks = bundle.get("tasks")
    if not isinstance(tasks, dict) or not tasks:
        raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", "tasks must be a non-empty object")

    bundle_task_keys = set(tasks.keys())
    if bundle_task_keys and not run_task_keys:
        raise PresentationValidationError(
            "PRESENTATION_SCHEMA_INVALID",
            "run has no tasks for bundled presentation",
        )

    if run_task_keys:
        missing_tasks = run_task_keys - set(tasks.keys())
        if missing_tasks:
            raise PresentationValidationError(
                "PRESENTATION_SCHEMA_INVALID",
                f"missing task presentation for: {', '.join(sorted(missing_tasks))}",
            )
        extra_tasks = set(tasks.keys()) - run_task_keys
        if extra_tasks:
            raise PresentationValidationError(
                "PRESENTATION_SCHEMA_INVALID",
                f"unknown task keys in presentation: {', '.join(sorted(extra_tasks))}",
            )

    for task_key, task_overlay in tasks.items():
        if not isinstance(task_overlay, dict):
            raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", f"task {task_key} must be an object")
        _require_non_empty_string(task_overlay.get("objective"), field=f"tasks.{task_key}.objective")

    workers = bundle.get("workers")
    if workers is not None:
        if not isinstance(workers, dict):
            raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", "workers must be an object")
        if run_worker_ids:
            worker_keys = set(workers.keys())
            if worker_keys != run_worker_ids:
                raise PresentationValidationError(
                    "PRESENTATION_SCHEMA_INVALID",
                    "worker presentation keys must match run workers",
                )
            for worker_id, worker_overlay in workers.items():
                if not isinstance(worker_overlay, dict):
                    raise PresentationValidationError(
                        "PRESENTATION_SCHEMA_INVALID",
                        f"worker {worker_id} must be an object",
                    )
                assigned = worker_overlay.get("assigned_task") or worker_overlay.get("display_name")
                _require_non_empty_string(assigned, field=f"workers.{worker_id}")

    claims = bundle.get("claims")
    if claims is not None:
        if not isinstance(claims, dict):
            raise PresentationValidationError("PRESENTATION_SCHEMA_INVALID", "claims must be an object")
        if run_claim_ids:
            claim_keys = set(claims.keys())
            if not claim_keys.issubset(run_claim_ids):
                unknown = claim_keys - run_claim_ids
                raise PresentationValidationError(
                    "PRESENTATION_SCHEMA_INVALID",
                    f"unknown claim ids in presentation: {', '.join(sorted(unknown))}",
                )
            for claim_id, statement in claims.items():
                if isinstance(statement, dict):
                    _require_non_empty_string(statement.get("statement"), field=f"claims.{claim_id}.statement")
                else:
                    _require_non_empty_string(statement, field=f"claims.{claim_id}")


def validate_demo_presentation_locales(
    presentations: dict[str, Any],
    *,
    run_task_keys: set[str],
    run_worker_ids: set[str],
    run_claim_ids: set[str],
    expected_run_id: UUID | None = None,
) -> list[str]:
    """Return reason codes; empty list means valid."""
    reason_codes: list[str] = []
    for locale in REQUIRED_LOCALES:
        bundle = presentations.get(locale)
        if not bundle:
            reason_codes.append(f"PRESENTATION_{locale.upper()}_MISSING")
            continue
        try:
            validate_presentation_bundle(
                bundle,
                locale=locale,
                run_task_keys=run_task_keys,
                run_worker_ids=run_worker_ids,
                run_claim_ids=run_claim_ids,
                expected_run_id=expected_run_id,
            )
        except PresentationValidationError as exc:
            reason_codes.append(exc.code)
    return reason_codes


def resolve_publication_presentations(
    snapshot: dict[str, Any] | None,
    slug: str,
) -> dict[str, Any]:
    """Merge stored snapshot presentation with bundled files for validation."""
    from deepscout_research.demo.presentation import load_bundled_presentation

    public = (snapshot or {}).get("public_demo") or {}
    stored = dict(public.get("presentation") or {})
    bundled = load_bundled_presentation(slug)
    merged = dict(stored)
    for locale, data in bundled.items():
        merged.setdefault(locale, data)
    return merged
