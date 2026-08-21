#!/usr/bin/env python3
"""Production zero-spend proof for anonymous demo browsing."""

from __future__ import annotations

import json
import subprocess
import sys

from sqlalchemy import text

from deepscout_core.settings import Settings
from deepscout_persistence.session import get_session_factory

DEMOS = [
    "eu-ai-act-gpai-2026",
    "rag-architecture-2026",
    "multi-hop-research",
    "ev-battery-evidence",
    "ev-lifecycle-evidence",
]
BASE = "https://deep-scout-plum.vercel.app"


def _counts(session) -> dict[str, int]:
    tables = (
        "token_usage_records",
        "tool_executions",
        "research_jobs",
        "chunk_embeddings",
    )
    out: dict[str, int] = {}
    for table in tables:
        try:
            out[table] = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        except Exception:
            out[table] = -1
    return out


def main() -> int:
    settings = Settings()
    session = get_session_factory(settings.database_url)()
    before = _counts(session)
    session.close()

    for slug in DEMOS:
        demo = subprocess.check_output(
            ["curl", "-sS", f"{BASE}/api/v1/demos/{slug}"],
            text=True,
        )
        run_id = json.loads(demo)["id"]
        paths = [
            f"/research/{run_id}",
            f"/research/{run_id}/plan",
            f"/research/{run_id}/workers",
            f"/research/{run_id}/sources",
            f"/research/{run_id}/claims",
            f"/research/{run_id}/report",
            f"/research/{run_id}/evaluations",
        ]
        for path in paths:
            subprocess.run(
                ["curl", "-sS", "-o", "/dev/null", f"{BASE}{path}"],
                check=False,
            )
        subprocess.run(
            [
                "curl",
                "-sS",
                "-o",
                "/dev/null",
                f"{BASE}/api/v1/research-runs/{run_id}/workspace",
            ],
            check=False,
        )

    session = get_session_factory(settings.database_url)()
    after = _counts(session)
    session.close()

    result = {
        "before": before,
        "after": after,
        "delta": {k: after[k] - before[k] for k in before},
        "pass": all(after[k] == before[k] for k in before if before[k] >= 0),
    }
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
