"""Scenario matrix: expected skip / run behavior for garden fixtures."""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "agentic_watering"))

from minutes_parse import clamp_run_minutes, parse_minutes  # noqa: E402
from probe_heuristics import probe_skip_recommendation, recommends_skip  # noqa: E402

# Golden scenarios: (name, plant, moisture, mock_reply, expect_skip, expect_run_min_range)
SCENARIOS = [
    (
        "zucchini_dry",
        "8 zucchini plants, 8 pea plants, and 8 eggplant plants",
        [21.0, 31.0],
        "Soil is very dry; full micro session.\nMINUTES: 20",
        False,
        (15, 25),
    ),
    (
        "tomato_below_target",
        "8 tomato plants",
        [38.0],
        "Below 45% target; soaker run.\nMINUTES: 18",
        False,
        (15, 25),
    ),
    (
        "peppers_wet",
        "Basil, parsley, kale, and peppers",
        [70.0],
        "Probe wet; skip.\nMINUTES: 12",
        True,
        (0, 0),
    ),
    (
        "storm_upcoming_zero",
        "Tall fescue lawn grass",
        [],
        "Heavy storms Sunday night POP 91%; skip tonight.\nMINUTES: 0",
        False,
        (0, 0),
    ),
]


class ScenarioMatrixTests(unittest.TestCase):
    def test_scenarios(self) -> None:
        for name, plant, moisture, reply, expect_skip, (lo, hi) in SCENARIOS:
            with self.subTest(name=name):
                hint = (
                    probe_skip_recommendation(
                        plant_profile=plant, moisture_values=moisture
                    )
                    if moisture
                    else "none (no probe)"
                )
                skip = recommends_skip(hint)
                self.assertEqual(skip, expect_skip, hint)
                parsed, minutes = parse_minutes(reply)
                self.assertTrue(parsed)
                run = clamp_run_minutes(minutes, parsed=parsed, probe_skip=skip)
                self.assertGreaterEqual(run, lo)
                self.assertLessEqual(run, hi)


if __name__ == "__main__":
    unittest.main()
