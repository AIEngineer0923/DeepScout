"""Tests for public demo presentation publication validation."""

from __future__ import annotations

from uuid import uuid4

import pytest

from deepscout_research.demo.catalog import DEMO_CATALOG
from deepscout_research.demo.presentation import load_bundled_presentation
from deepscout_research.demo.presentation_validation import (
    PRESENTATION_VERSION,
    PresentationValidationError,
    validate_demo_presentation_locales,
    validate_presentation_bundle,
)


def _valid_bundle(locale: str = "en") -> dict:
    return {
        "version": PRESENTATION_VERSION,
        "locale": locale,
        "goal": "Compare credible evidence on a technical topic with citations.",
        "title": "Technical evidence comparison",
        "summary": "Evidence-heavy synthesis from primary sources.",
        "why_interesting": "Demonstrates provenance and structured research output.",
        "tasks": {
            "task_a": {
                "objective": "Investigate the primary technical evidence base for the topic.",
                "display_name": "Investigate evidence",
            }
        },
        "workers": {
            str(uuid4()): {
                "display_name": "Researcher 1",
                "assigned_task": "Investigate the primary technical evidence base for the topic.",
            }
        },
        "report": {
            "title": "Research Report",
            "body_markdown": "# Research Report\n\n" + ("Evidence paragraph. " * 12),
        },
        "claims": {},
    }


def test_valid_bundle_passes():
    worker_id = str(uuid4())
    bundle = _valid_bundle()
    bundle["workers"] = {
        worker_id: {
            "display_name": "Researcher 1",
            "assigned_task": "Investigate the primary technical evidence base for the topic.",
        }
    }
    validate_presentation_bundle(
        bundle,
        locale="en",
        run_task_keys={"task_a"},
        run_worker_ids={worker_id},
        run_claim_ids=set(),
    )


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (lambda b: b.pop("goal"), "PRESENTATION_SCHEMA_INVALID"),
        (lambda b: b.pop("report"), "PRESENTATION_SCHEMA_INVALID"),
        (lambda b: b.setdefault("tasks", {}).pop("task_a"), "PRESENTATION_SCHEMA_INVALID"),
        (lambda b: b.update({"version": 99}), "PRESENTATION_VERSION_UNSUPPORTED"),
        (lambda b: b.update({"run_id": str(uuid4())}), "PRESENTATION_SCHEMA_INVALID"),
    ],
)
def test_invalid_bundle_cases(mutator, code):
    bundle = _valid_bundle()
    worker_id = next(iter(bundle["workers"]))
    mutator(bundle)
    with pytest.raises(PresentationValidationError) as exc:
        validate_presentation_bundle(
            bundle,
            locale="en",
            run_task_keys={"task_a"},
            run_worker_ids={worker_id},
            run_claim_ids=set(),
            expected_run_id=uuid4(),
        )
    assert exc.value.code == code


def test_missing_locale_reports_reason_code():
    codes = validate_demo_presentation_locales(
        {"en": _valid_bundle("en")},
        run_task_keys={"task_a"},
        run_worker_ids=set(),
        run_claim_ids=set(),
    )
    assert codes == ["PRESENTATION_IT_MISSING"]


def test_malformed_bundle_reports_schema_invalid():
    codes = validate_demo_presentation_locales(
        {"en": {"goal": "x"}, "it": _valid_bundle("it")},
        run_task_keys=set(),
        run_worker_ids=set(),
        run_claim_ids=set(),
    )
    assert "PRESENTATION_SCHEMA_INVALID" in codes


def test_unknown_task_key_fails():
    bundle = _valid_bundle()
    with pytest.raises(PresentationValidationError):
        validate_presentation_bundle(
            bundle,
            locale="en",
            run_task_keys={"other_task"},
            run_worker_ids=set(),
            run_claim_ids=set(),
        )


def test_all_catalog_bundles_have_valid_en_it_schema():
    for entry in DEMO_CATALOG:
        bundled = load_bundled_presentation(entry["slug"])
        assert "en" in bundled, entry["slug"]
        assert "it" in bundled, entry["slug"]
        for locale in ("en", "it"):
            validate_presentation_bundle(
                bundled[locale],
                locale=locale,
                run_task_keys=set(bundled[locale].get("tasks", {}).keys()),
                run_worker_ids=set(),
                run_claim_ids=set(bundled[locale].get("claims", {}).keys()),
            )


def test_empty_required_goal_fails():
    bundle = _valid_bundle()
    bundle["goal"] = "short"
    with pytest.raises(PresentationValidationError):
        validate_presentation_bundle(
            bundle,
            locale="en",
            run_task_keys=set(),
            run_worker_ids=set(),
            run_claim_ids=set(),
        )
