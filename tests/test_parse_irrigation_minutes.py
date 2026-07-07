"""Unit tests for MINUTES: line parsing (no LLM calls)."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from irrigation_prompt import parse_minutes


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


if __name__ == "__main__":
    unittest.main()
