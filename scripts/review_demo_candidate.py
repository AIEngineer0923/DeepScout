"""Operator quality review for a candidate public demo run."""

from __future__ import annotations

import argparse
import json
from uuid import UUID

from deepscout_core.settings import Settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.demo.quality import review_demo_candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--slug")
    args = parser.parse_args()
    settings = Settings()
    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    try:
        payload = review_demo_candidate(store, UUID(args.run_id), slug=args.slug)
    finally:
        session.close()
    print(json.dumps(payload, indent=2))
    return 0 if payload["PUBLICATION_DECISION"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
