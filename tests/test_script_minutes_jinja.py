"""Render the real MINUTES templates from the watering script package.

The Python helpers in ``irrigation_prompt`` and ``minutes_parse`` only mirror
the Jinja that actually runs in Home Assistant, so a mirror-only test suite
missed the emphasis bug that discarded correct answers live. This exercises the
templates lifted straight out of the YAML with Home Assistant's filter and test
semantics.
"""

from __future__ import annotations

import pathlib
import re
import unittest

try:
    import yaml
    from jinja2 import Environment
except ImportError:  # pragma: no cover - optional local dependency
    yaml = None
    Environment = None

SCRIPT_YAML = (
    pathlib.Path(__file__).resolve().parents[1]
    / "custom_components"
    / "agentic_watering"
    / "packages"
    / "smart_sequential_watering_script.yaml"
)

TEMPLATE_KEYS = ("llm_minutes_parsed", "llm_minutes")


def _ha_regex_replace(value="", find="", replace="", ignorecase=False):
    return re.compile(find, re.I if ignorecase else 0).sub(replace, str(value))


def _ha_regex_match(value, find="", ignorecase=False):
    return bool(re.match(find, str(value), re.I if ignorecase else 0))


def _ha_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "on", "1")
    return bool(value)


def _collect_templates(node, out):
    """Gather every MINUTES template in the package, at any nesting depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in TEMPLATE_KEYS and isinstance(value, str) and "{%" in value:
                out.setdefault(key, []).append(value)
            _collect_templates(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect_templates(item, out)
    return out


@unittest.skipIf(yaml is None or Environment is None, "PyYAML/Jinja2 not installed")
class ScriptMinutesTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.env = Environment()
        cls.env.filters["regex_replace"] = _ha_regex_replace
        cls.env.filters["bool"] = _ha_bool
        cls.env.tests["match"] = _ha_regex_match
        cls.templates = _collect_templates(
            yaml.safe_load(SCRIPT_YAML.read_text(encoding="utf-8")), {}
        )

    def _render_all(self, key: str, raw: str) -> list[str]:
        found = self.templates.get(key) or []
        self.assertTrue(found, f"no {key} template found in the script package")
        return [
            self.env.from_string(t).render(zone_llm_raw=raw).strip() for t in found
        ]

    def _parse(self, raw: str) -> tuple[bool, int]:
        parsed = self._render_all("llm_minutes_parsed", raw)
        minutes = self._render_all("llm_minutes", raw)
        # Initial call and retry blocks must not disagree.
        self.assertEqual(len(set(parsed)), 1, f"parsed templates disagree: {parsed}")
        self.assertEqual(len(set(minutes)), 1, f"minutes templates disagree: {minutes}")
        return _ha_bool(parsed[0]), int(minutes[0])

    def test_plain_answer(self) -> None:
        self.assertEqual(self._parse("Rain is coming.\nMINUTES: 0"), (True, 0))

    def test_emphasised_answers_from_live_runs(self) -> None:
        cases = (
            ("**MINUTES: 20**", 20),
            ("**MINUTES:** 12", 12),
            ("**MINUTES: 7**\n\nReassess.\n\n**MINUTES: 7**", 7),
            ("### MINUTES: 5", 5),
            ("MINUTES: 20 minutes.", 20),
            ("`MINUTES: 9`", 9),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(self._parse(raw), (True, expected))

    def test_clamped_to_25(self) -> None:
        self.assertEqual(self._parse("**MINUTES: 99**"), (True, 25))

    def test_prose_is_not_parsed(self) -> None:
        self.assertEqual(
            self._parse("I would water for **20 minutes** today."), (False, 0)
        )

    def test_last_answer_wins(self) -> None:
        self.assertEqual(
            self._parse("**MINUTES: 25**\nToo much.\nMINUTES: 6"), (True, 6)
        )


if __name__ == "__main__":
    unittest.main()
