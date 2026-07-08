"""Assembly tests for goal-framed irrigation prompts."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "agentic_watering"))

from irrigation_prompt import (  # noqa: E402
    EAST_LAWN_PROFILE,
    build_system_prompt,
    build_user_prompt,
    has_unresolved_placeholder,
    hourly_precip,
    numbered_steps_on_separate_lines,
)
from plant_knowledge import format_knowledge_block, resolve_water_requirement_mm  # noqa: E402


class PromptAssemblyTests(unittest.TestCase):
    def test_east_lawn_failure_payload_assembly(self) -> None:
        pk = resolve_water_requirement_mm(
            EAST_LAWN_PROFILE["plant_profile"],
            climate_setting="temperate_humid",
        )
        self.assertTrue(pk["found"])
        knowledge = format_knowledge_block(pk)
        self.assertIn("15", knowledge)
        self.assertIn("plant-knowledge MCP", knowledge)

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(
            days_since=2,
            last_run_minutes="10",
            knowledge_block=knowledge,
            garden_temp_f=72.0,
            garden_peak_f=75.0,
            open_meteo=hourly_precip([0.0] * 48 + [42.4] + [0.0] * 23),
            forecast_short=[],
        )

        self.assertFalse(has_unresolved_placeholder(system_prompt))
        self.assertFalse(has_unresolved_placeholder(user_prompt))
        self.assertNotIn("<FILL", user_prompt.upper())
        self.assertTrue(numbered_steps_on_separate_lines(system_prompt))
        self.assertIn("Days since last irrigation: 2", user_prompt)
        self.assertIn("weekly water need", user_prompt)

    def test_placeholder_guard_detects_fill_token(self) -> None:
        blob = "Days since last irrigation: <FILL IN — e.g. 2>"
        self.assertTrue(has_unresolved_placeholder(blob))

    def test_placeholder_guard_ignores_nested_json(self) -> None:
        blob = 'Open-Meteo past 72h precipitation: {"hourly_mm": [{"t": "2026-07-07T12:00", "mm": 0.0}]}'
        self.assertFalse(has_unresolved_placeholder(blob))

    def test_placeholder_guard_detects_unrendered_jinja(self) -> None:
        blob = "Days since last irrigation: {{ days_since }}"
        self.assertTrue(has_unresolved_placeholder(blob))

    def test_corn_plant_profile_resolves(self) -> None:
        pk = resolve_water_requirement_mm("24 corn plants", climate_setting="temperate_humid")
        self.assertTrue(pk["found"], pk)
        knowledge = format_knowledge_block(pk)
        self.assertIn("plant-knowledge MCP", knowledge)
        self.assertIn("Sweet corn", knowledge)

    def test_mixed_veg_zone_resolves(self) -> None:
        pk = resolve_water_requirement_mm(
            "8 zucchini plants, 8 pea plants, and 8 eggplant plants",
            climate_setting="temperate_humid",
        )
        self.assertTrue(pk["found"], pk)


if __name__ == "__main__":
    unittest.main()
