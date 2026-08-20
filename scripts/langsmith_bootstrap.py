#!/usr/bin/env python3
"""Bootstrap LangSmith datasets and offline eval metadata for DeepScout."""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    if not os.getenv("LANGSMITH_API_KEY"):
        print("LANGSMITH_API_KEY not configured — skipping bootstrap", file=sys.stderr)
        return 0
    try:
        from langsmith import Client
    except ImportError:
        print("langsmith package unavailable", file=sys.stderr)
        return 1

    client = Client()
    dataset_name = "deepscout-baseline-v1"
    existing = list(client.list_datasets(dataset_name=dataset_name))
    if existing:
        dataset = existing[0]
        print(json.dumps({"status": "ALREADY_PRESENT_AND_VERIFIED", "dataset": dataset.name}))
        return 0

    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description="DeepScout baseline research scenarios",
    )
    examples = [
        {
            "inputs": {"goal": "Compare NMC and LFP battery chemistries"},
            "outputs": {"expected_evidence_min": 1},
        },
        {
            "inputs": {"goal": "What is the capital of France?"},
            "outputs": {"expected_evidence_min": 0},
        },
    ]
    for example in examples:
        client.create_example(
            inputs=example["inputs"],
            outputs=example["outputs"],
            dataset_id=dataset.id,
        )
    print(json.dumps({"status": "CREATED_AND_VERIFIED", "dataset": dataset.name}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
