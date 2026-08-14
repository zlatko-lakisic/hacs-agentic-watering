"""Unit tests for soil probe SKIP heuristics and minute bands."""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "agentic_watering"))

from minutes_parse import clamp_run_minutes, parse_minutes  # noqa: E402
from probe_heuristics import (  # noqa: E402
    probe_skip_recommendation,
    recommends_skip,
    soil_adjustment_guide,
)


class ProbeHeuristicsTests(unittest.TestCase):
    def test_tomato_38_does_not_generic_skip(self) -> None:
        hint = probe_skip_recommendation(
            plant_profile="8 tomato plants", moisture_values=[38.0]
        )
        self.assertFalse(recommends_skip(hint), hint)
        self.assertIn("WATER OK", hint)

    def test_tomato_in_band_skips(self) -> None:
        hint = probe_skip_recommendation(
            plant_profile="tomato", moisture_values=[50.0]
        )
        self.assertTrue(recommends_skip(hint))

    def test_peppers_wet_skips(self) -> None:
        hint = probe_skip_recommendation(
            plant_profile="Basil, parsley, kale, and peppers",
            moisture_values=[70.0],
        )
        self.assertTrue(recommends_skip(hint))

    def test_zucchini_very_dry_water_ok(self) -> None:
        hint = probe_skip_recommendation(
            plant_profile="8 zucchini plants, 8 pea plants, and 8 eggplant plants",
            moisture_values=[21.0, 31.0],
        )
        self.assertFalse(recommends_skip(hint), hint)

    def test_guide_rejects_token_runs(self) -> None:
        guide = soil_adjustment_guide("zucchini eggplant")
        self.assertIn("15-25", guide)
        self.assertNotIn("add 3-6 min", guide.lower())


class MinutesParseModuleTests(unittest.TestCase):
    def test_parse_and_clamp(self) -> None:
        ok, m = parse_minutes("Need water.\nMINUTES: 18")
        self.assertTrue(ok)
        self.assertEqual(m, 18)
        self.assertEqual(clamp_run_minutes(18, parsed=True, probe_skip=False), 18)
        self.assertEqual(clamp_run_minutes(18, parsed=True, probe_skip=True), 0)
        self.assertEqual(clamp_run_minutes(1, parsed=True, probe_skip=False), 0)


if __name__ == "__main__":
    unittest.main()
