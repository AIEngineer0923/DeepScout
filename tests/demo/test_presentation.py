from deepscout_research.demo.presentation import (
    build_presentation_payload,
    normalize_locale,
    resolve_presentation,
)


def test_normalize_locale_defaults_to_en():
    assert normalize_locale(None) == "en"
    assert normalize_locale("it-IT") == "it"
    assert normalize_locale("fr") == "en"


def test_resolve_presentation_from_bundled_files():
    pres = resolve_presentation(None, "multi-hop-research", "it")
    assert pres is not None
    assert pres["goal"]


def test_build_presentation_payload_overlays_tasks():
    workspace = {
        "goal": "English",
        "tasks": [{"id": "1", "task_key": "a", "objective": "English task", "display_name": "W01"}],
        "workers": [],
        "claims": [],
        "report": None,
    }
    presentation = {
        "goal": "Italiano",
        "tasks": {"a": {"objective": "Attività italiana", "display_name": "W01 IT"}},
    }
    payload = build_presentation_payload(workspace, presentation, locale="it")
    assert payload["goal"] == "Italiano"
    assert payload["tasks"]["a"]["objective"] == "Attività italiana"
