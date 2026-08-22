#!/usr/bin/env python3
"""Export EN/IT presentation bundles from a completed demo candidate run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from deepscout_core.settings import Settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.demo.export import build_presentation_bundle_from_run
from deepscout_research.demo.presentation import merge_presentation_into_public_demo
from deepscout_research.demo.quality import review_demo_candidate

_DATA_DIR = (
    Path(__file__).resolve().parents[1]
    / "libs/research/src/deepscout_research/demo/presentation_data"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--attach-db", action="store_true")
    args = parser.parse_args()

    run_id = UUID(args.run_id)
    slug = args.slug.strip().lower()
    settings = Settings()
    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    try:
        en = build_presentation_bundle_from_run(store, run_id, slug=slug, locale="en")
        en_path = _DATA_DIR / f"{slug}.en.json"
        en_path.write_text(json.dumps(en, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {en_path}")

        it_path = _DATA_DIR / f"{slug}.it.json"
        if it_path.exists():
            it = json.loads(it_path.read_text(encoding="utf-8"))
            it["run_id"] = str(run_id)
            it["tasks"] = en["tasks"]
            it["workers"] = en["workers"]
            it["claims"] = en["claims"]
            if not it.get("report", {}).get("body_markdown"):
                it.setdefault("report", {})["body_markdown"] = en["report"]["body_markdown"]
            it_path.write_text(json.dumps(it, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Updated run bindings in {it_path}")

        if args.attach_db:
            row = store.get_run_row(run_id)
            if row is None:
                raise LookupError("run not found")
            snap = dict(row.config_snapshot or {})
            public_demo = merge_presentation_into_public_demo(
                {**(snap.get("public_demo") or {}), "slug": slug},
                slug,
            )
            store.merge_config_snapshot(run_id, {"public_demo": public_demo})
            store.commit()
            review = review_demo_candidate(store, run_id, slug=slug)
            print(json.dumps(review, indent=2))
            return 0 if review["PUBLICATION_DECISION"] in {"PASS", "WARN"} else 1
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
