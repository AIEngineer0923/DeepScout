"""Operator-only demo publication. Never expose this as a public HTTP route."""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from deepscout_core.settings import get_settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.demo.publication import publish_demo, unpublish_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish or unpublish a public demo run")
    parser.add_argument("run_id")
    parser.add_argument("--slug", help="Public slug (required to publish)")
    parser.add_argument("--unpublish", action="store_true")
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
