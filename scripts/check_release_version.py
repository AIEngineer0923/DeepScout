#!/usr/bin/env python3
"""Fail when DeepScout's release-facing version declarations drift."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECTS = (
    "pyproject.toml",
    "apps/api/pyproject.toml",
    "libs/core/pyproject.toml",
    "libs/providers/pyproject.toml",
    "libs/research/pyproject.toml",
    "libs/persistence/pyproject.toml",
    "libs/evaluation/pyproject.toml",
)


def project_version(path: str) -> str:
    with (ROOT / path).open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Release tag to verify, for example v0.1.0")
    args = parser.parse_args()

    canonical = project_version("pyproject.toml")
    declared = {path: project_version(path) for path in PYPROJECTS}
    web_package = json.loads((ROOT / "apps/web/package.json").read_text())
    web_lock = json.loads((ROOT / "apps/web/package-lock.json").read_text())
    declared["apps/web/package.json"] = str(web_package["version"])
    declared["apps/web/package-lock.json"] = str(web_lock["version"])

    mismatches = {path: value for path, value in declared.items() if value != canonical}
    if mismatches:
        print(f"Canonical version: {canonical}", file=sys.stderr)
        for path, value in mismatches.items():
            print(f"Version mismatch: {path} declares {value}", file=sys.stderr)
        return 1

    if args.tag:
        expected_tag = f"v{canonical}"
        if args.tag != expected_tag:
            print(
                f"Tag mismatch: expected {expected_tag} from pyproject.toml, got {args.tag}",
                file=sys.stderr,
            )
            return 1
        notes = ROOT / "docs" / "releases" / f"{args.tag}.md"
        if not notes.is_file():
            print(f"Missing release notes: {notes.relative_to(ROOT)}", file=sys.stderr)
            return 1

    print(f"DeepScout release version: {canonical}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
