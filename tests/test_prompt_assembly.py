"""Assembly tests for goal-framed irrigation prompts."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "agentic_watering"))

from irrigation_prompt import (  # noqa: E402
    build_system_prompt,
    build_user_prompt,
    has_unresolved_placeholder,
    hourly_precip,
    numbered_steps_on_separate_lines,
)


class PromptAssemblyTests(unittest.TestCase):
    def test_east_lawn_facts_only_assembly(self) -> None:
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(
            days_since=2,
            last_run_minutes=10,
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
        self.assertIn("Home Assistant only supplies sensor and zone facts", system_prompt)
        self.assertNotIn("plant-knowledge MCP", user_prompt)
        self.assertNotIn("weekly water need", user_prompt)

    def test_missing_facts_default_to_safe_values(self) -> None:
        user_prompt = build_user_prompt()
        self.assertIn("Days since last irrigation: 0", user_prompt)
        self.assertIn("Last run duration (minutes): 0", user_prompt)
        self.assertIn("Garden temperature now (F): unknown", user_prompt)
        self.assertIn('"precipitation_mm_sum": 0', user_prompt)
        self.assertIn('"weather_provider": "none"', user_prompt)

    def test_placeholder_guard_detects_fill_token(self) -> None:
        blob = "Days since last irrigation: <FILL IN — e.g. 2>"
        self.assertTrue(has_unresolved_placeholder(blob))

    def test_placeholder_guard_ignores_nested_json(self) -> None:
        blob = 'Open-Meteo past 72h precipitation: {"hourly_mm": [{"t": "2026-07-07T12:00", "mm": 0.0}]}'
        self.assertFalse(has_unresolved_placeholder(blob))

    def test_placeholder_guard_detects_unrendered_jinja(self) -> None:
        blob = "Days since last irrigation: {{ days_since }}"
        self.assertTrue(has_unresolved_placeholder(blob))


if __name__ == "__main__":
    unittest.main()
