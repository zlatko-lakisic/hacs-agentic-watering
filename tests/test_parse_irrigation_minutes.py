"""Unit tests for MINUTES: line parsing (no LLM calls)."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(
    0,
    str(
        pathlib.Path(__file__).resolve().parents[1]
        / "custom_components"
        / "agentic_watering"
    ),
)

from irrigation_prompt import parse_minutes
from minutes_parse import parse_minutes as parse_minutes_service


class ParseIrrigationMinutesTests(unittest.TestCase):
    def test_parses_final_minutes_line(self) -> None:
        raw = "Rain was heavy.\nMINUTES: 0"
        ok, minutes = parse_minutes(raw)
        self.assertTrue(ok)
        self.assertEqual(minutes, 0)

    def test_last_minutes_line_wins(self) -> None:
        raw = "MINUTES: 9\nMore text\nMINUTES: 3"
        ok, minutes = parse_minutes(raw)
        self.assertTrue(ok)
        self.assertEqual(minutes, 3)

    def test_clamps_to_25(self) -> None:
        ok, minutes = parse_minutes("MINUTES: 99")
        self.assertTrue(ok)
        self.assertEqual(minutes, 25)

    def test_parse_failure_does_not_guess(self) -> None:
        ok, minutes = parse_minutes("I think about 7 minutes would work.")
        self.assertFalse(ok)
        self.assertEqual(minutes, 0)

    def test_ignores_bare_integer(self) -> None:
        ok, minutes = parse_minutes("7")
        self.assertFalse(ok)
        self.assertEqual(minutes, 0)


class MarkdownEmphasisTests(unittest.TestCase):
    """Replies seen live on 2026-08-16/17 that were discarded as unreadable.

    Each answer was correct; the emphasis made the parser fail closed, so dry
    zones (zucchini at 21% soil moisture) were skipped instead of watered.
    """

    CASES = (
        ("zucchini bold answer", "Soil is critically low.\n\n**MINUTES: 20**", 20),
        ("corn bold label", "Rain starts tomorrow.\n\n**MINUTES:** 12", 12),
        ("slope repeated bold", "**MINUTES: 7**\n\nReassess later.\n\n**MINUTES: 7**", 7),
        ("kitchen lawn bold zero", "Enough rain fell.\n\n**MINUTES: 0**", 0),
        ("heading form", "### MINUTES: 5", 5),
        ("trailing unit", "MINUTES: 20 minutes.", 20),
        ("backticks", "`MINUTES: 9`", 9),
    )

    def test_both_parsers_accept_emphasised_answers(self) -> None:
        for name, raw, expected in self.CASES:
            for label, parser in (
                ("script", parse_minutes),
                ("service", parse_minutes_service),
            ):
                with self.subTest(case=name, parser=label):
                    ok, minutes = parser(raw)
                    self.assertTrue(ok, f"{name} not parsed by {label} parser")
                    self.assertEqual(minutes, expected)

    def test_emphasis_does_not_loosen_prose(self) -> None:
        prose = "I would water for **20 minutes** given how dry it is."
        for label, parser in (
            ("script", parse_minutes),
            ("service", parse_minutes_service),
        ):
            with self.subTest(parser=label):
                ok, minutes = parser(prose)
                self.assertFalse(ok)
                self.assertEqual(minutes, 0)

    def test_last_answer_still_wins_with_emphasis(self) -> None:
        raw = "**MINUTES: 25**\nOn reflection that is too much.\nMINUTES: 6"
        for label, parser in (
            ("script", parse_minutes),
            ("service", parse_minutes_service),
        ):
            with self.subTest(parser=label):
                ok, minutes = parser(raw)
                self.assertTrue(ok)
                self.assertEqual(minutes, 6)


if __name__ == "__main__":
    unittest.main()
