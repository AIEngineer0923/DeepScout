#!/usr/bin/env python3
"""Create and verify LangSmith workspace code evaluators for DeepScout."""

from __future__ import annotations

import asyncio
import json
import os
import sys

import httpx
from deepscout_research.langsmith_env import configure_langsmith_env

CODE_EVALUATOR = """
def perform_eval(run, example):
    outputs = run.outputs or {}
    evidence = outputs.get("evidence_count", 0)
    return {"key": "claim_has_evidence", "score": 1 if evidence else 0}
"""


async def main() -> int:
    settings = configure_langsmith_env()
    if settings.langsmith_api_key is None:
        print("LANGSMITH_API_KEY not configured", file=sys.stderr)
        return 1

    from langsmith import Client

    client = Client()
    existing = [
        item
        async for item in client.evaluators.list(
            name_contains="deepscout-claim-has-evidence", limit=20, timeout=30.0
        )
    ]
    if existing:
        evaluator_id = str(
            getattr(existing[0], "id", None) or getattr(existing[0], "evaluator", existing[0])
        )
        print(
            json.dumps({"status": "ALREADY_PRESENT", "evaluator": "deepscout-claim-has-evidence"})
        )
    else:
        created = await client.evaluators.create(
            name="deepscout-claim-has-evidence",
            type="code",
            code_evaluator={"code": CODE_EVALUATOR.strip(), "language": "python"},
            timeout=30.0,
        )
        evaluator_id = str(created.evaluator.id)
        print(json.dumps({"status": "CREATED", "evaluator_id": evaluator_id}))

    project = client.read_project(project_name=settings.langsmith_project)
    endpoint = os.environ.get("LANGSMITH_ENDPOINT", "https://eu.api.smith.langchain.com")
    api_key = settings.langsmith_api_key.get_secret_value()
    listed = httpx.get(
        f"{endpoint}/api/v1/runs/rules",
        headers={"x-api-key": api_key},
        params={"session_id": str(project.id)},
        timeout=30.0,
    )
    attached = False
    if listed.status_code == 200:
        payload = listed.json()
        rules = (
            payload
            if isinstance(payload, list)
            else payload.get("rules") or payload.get("data") or []
        )
        attached = any("deepscout-claim-has-evidence" in str(rule) for rule in rules)
    if not attached:
        response = httpx.post(
            f"{endpoint}/api/v1/runs/rules",
            headers={"x-api-key": api_key},
            json={
                "display_name": "deepscout-root-claim-has-evidence",
                "session_id": str(project.id),
                "sampling_rate": 1.0,
                "filter": "and(eq(is_root, true), eq(name, research_run_execute))",
                "evaluator_id": evaluator_id,
                "is_enabled": True,
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            print(
                json.dumps(
                    {
                        "status": "EVALUATOR_CREATED_RULE_API_LIMITATION",
                        "http_status": response.status_code,
                        "manual_path": "EU LangSmith → Tracing Projects → deepscout-dev → Evaluators → Attach existing → deepscout-claim-has-evidence → filter root research_run_execute → sampling 100% for cheap code eval",
                    }
                )
            )
            return 0
        attached = True
    print(json.dumps({"status": "ONLINE_READY", "attached": attached, "sampling_rate": 1.0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
