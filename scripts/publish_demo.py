"""Operator-only demo publication. Never expose this as a public HTTP route."""

from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

from deepscout_core.settings import get_settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.demo.publication import publish_demo, unpublish_demo
from deepscout_research.demo.quality import review_demo_candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish or unpublish a public demo run")
    parser.add_argument("run_id")
    parser.add_argument("--slug", help="Public slug (required to publish)")
    parser.add_argument("--unpublish", action="store_true")
    parser.add_argument("--force-warn", action="store_true", help="Allow WARN quality verdict")
    args = parser.parse_args(argv)
    run_id = UUID(args.run_id)
    settings = get_settings()
    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    try:
        if args.unpublish:
            row = unpublish_demo(store, run_id)
        else:
            if not args.slug:
                parser.error("--slug is required unless --unpublish")
            review = review_demo_candidate(store, run_id, slug=args.slug)
            if review["PUBLICATION_DECISION"] == "FAIL":
                print(json.dumps(review, indent=2), file=sys.stderr)
                raise SystemExit("quality gate FAIL — not published")
            if review["PUBLICATION_DECISION"] == "WARN" and not args.force_warn:
                print(json.dumps(review, indent=2), file=sys.stderr)
                raise SystemExit("quality gate WARN — pass --force-warn to publish")
            row = publish_demo(store, run_id, args.slug)
        store.commit()
        print(f"run={row.id} public_demo={row.is_public_demo} slug={row.public_slug or '-'}")
        return 0
    except (LookupError, ValueError) as exc:
        session.rollback()
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
