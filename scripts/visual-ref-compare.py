#!/usr/bin/env python3
"""Local-only reference screenshot geometry report. Never commits private PNGs."""

from __future__ import annotations

import json
from pathlib import Path

REFS = Path.home() / "Downloads" / "DeepScout"
FIXTURE_RUN = "11111111-1111-4111-8111-111111111111"
RUN = f"/research/{FIXTURE_RUN}"

SCREEN_MAP = [
    ("dashboard", "C0BA50FD-E7F7-4DF8-B062-D4C7EDE1B05D.PNG", "/"),
    ("new-research", "E52F3569-5FDB-4277-8EB1-CDCCBD60305D.PNG", "/research/new"),
    ("live-research", "A90D5378-EE66-42CF-879D-DD9D7CBF9397.PNG", RUN),
    ("plan", "EFA3D5E4-F14C-461C-8C38-8F4E26FAA57E.PNG", f"{RUN}/plan"),
    ("workers", "06BFB966-D14C-4EC6-A5F8-5F5281D7433C.PNG", f"{RUN}/workers"),
    ("sources", "C4440FB0-4D22-4BF3-88A5-DF72AB8B9A4C.PNG", f"{RUN}/sources"),
    ("snapshot", "772A034C-F648-48D5-B7C0-9738DE43D6B8.PNG", f"{RUN}/snapshots"),
    ("claims", "43EA5FA1-D97C-49CD-BD9F-A9B7E08876FC.PNG", f"{RUN}/claims"),
    ("quality", "8A2D89CA-5E26-49B9-9396-7C122E12CB9D.PNG", f"{RUN}/quality"),
    ("report", "2CCA152F-DB82-4916-ABB5-44D30A3A3C66.PNG", f"{RUN}/report"),
    ("evaluations", "B9DEB6CA-FEB5-4DA3-8573-065F3747DEBE.PNG", f"{RUN}/evaluations"),
    ("history", "528501AB-87FE-44F0-88CC-A54B67F4D062.PNG", "/history"),
    ("resume", "A38A68F7-6179-4734-8E0F-9E1B6D2F5A43.PNG", f"/resume/{FIXTURE_RUN}"),
    ("settings", "B5D6636A-2156-49F4-9A44-1424D03C4FD3.PNG", "/settings"),
]

DESIGN_TOKENS = {
    "sidebar_width_px": 248,
    "header_height_px": 64,
    "detail_panel_width_px": 320,
    "tab_height_px": 42,
    "control_height_px": 40,
    "card_radius_px": 12,
}


def ref_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return None
    with Image.open(path) as img:
        return img.size


def main() -> int:
    rows: list[dict[str, object]] = []
    for screen, ref_name, route in SCREEN_MAP:
        ref_path = REFS / ref_name
        size = ref_size(ref_path) if ref_path.exists() else None
        rows.append(
            {
                "screen": screen,
                "reference": str(ref_path),
                "route": route,
                "reference_viewport": {"width": size[0], "height": size[1]} if size else None,
                "app_viewport": {"width": 1536, "height": 1024},
                "design_tokens": DESIGN_TOKENS,
                "reference_exists": ref_path.exists(),
            }
        )
    note = "Use Playwright baselines for app-side regression; maps local refs only."
    payload = {
        "screens": rows,
        "note": note,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
