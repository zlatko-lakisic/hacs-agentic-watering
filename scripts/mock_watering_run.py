#!/usr/bin/env python3
"""Pre-deploy mock watering run — no valves, no Jetson required.

Exercises probe heuristics + MINUTES parse against golden fixtures.
Exit non-zero on mismatch.

Usage:
  python scripts/mock_watering_run.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "agentic_watering"))
sys.path.insert(0, str(ROOT / "tests"))

from minutes_parse import clamp_run_minutes, parse_minutes  # noqa: E402
from probe_heuristics import (  # noqa: E402
    probe_skip_recommendation,
    recommends_skip,
    soil_adjustment_guide,
)

FIXTURES = [
    {
        "label": "Zucchini",
        "plant_profile": "8 zucchini plants, 8 pea plants, and 8 eggplant plants",
        "moisture": [21.0, 31.0],
        "mock_reply": "Very dry; full micro session required.\nMINUTES: 20",
        "expect_run_min": 20,
        "expect_skip": False,
    },
    {
        "label": "Tomato",
        "plant_profile": "8 tomato plants",
        "moisture": [38.0],
        "mock_reply": "Below tomato target 45%.\nMINUTES: 18",
        "expect_run_min": 18,
        "expect_skip": False,
    },
    {
        "label": "Peppers and Kale",
        "plant_profile": "Basil, parsley, kale, and peppers",
        "moisture": [70.0],
        "mock_reply": "Wet enough.\nMINUTES: 10",
        "expect_run_min": 0,
        "expect_skip": True,
    },
    {
        "label": "Kitchen Lawn",
        "plant_profile": "Tall fescue lawn grass",
        "moisture": [],
        "mock_reply": "Sunday storms POP 91%; skip.\nMINUTES: 0",
        "expect_run_min": 0,
        "expect_skip": False,
    },
]


def main() -> int:
    report = []
    failed = 0
    for fx in FIXTURES:
        hint = (
            probe_skip_recommendation(
                plant_profile=fx["plant_profile"], moisture_values=fx["moisture"]
            )
            if fx["moisture"]
            else "none (no probe)"
        )
        skip = recommends_skip(hint)
        parsed, minutes = parse_minutes(fx["mock_reply"])
        run = clamp_run_minutes(minutes, parsed=parsed, probe_skip=skip)
        ok = skip == fx["expect_skip"] and run == fx["expect_run_min"] and parsed
        if not ok:
            failed += 1
        report.append(
            {
                "label": fx["label"],
                "probe_hint": hint,
                "skip": skip,
                "minutes": minutes,
                "run_minutes": run,
                "guide_snip": soil_adjustment_guide(fx["plant_profile"])[:80],
                "ok": ok,
            }
        )
    print(json.dumps({"failed": failed, "zones": report}, indent=2))
    if failed:
        print(f"FAIL: {failed} zone(s) mismatched golden expectations", file=sys.stderr)
        return 1
    print("OK: mock watering matrix passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
