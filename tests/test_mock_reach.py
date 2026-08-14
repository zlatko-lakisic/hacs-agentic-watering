"""Offline test: mock Reach chat wiring for plan_zone_minutes helpers."""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "custom_components" / "agentic_watering"))

from mock_reach import MockSessionBridge  # noqa: E402
from minutes_parse import clamp_run_minutes, parse_minutes  # noqa: E402


class MockReachChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_mock_bridge_returns_minutes(self) -> None:
        bridge = MockSessionBridge(reply_text="Dry zucchini.\nMINUTES: 22")
        await bridge.start()
        result = await bridge.chat(
            text="plan zone",
            run_mode="dynamic",
            selected_agent_provider_ids=["client.irrigation_planner"],
        )
        self.assertEqual(result["questionId"], "mock-qid-1")
        ok, minutes = parse_minutes(result["text"])
        self.assertTrue(ok)
        self.assertEqual(clamp_run_minutes(minutes, parsed=True, probe_skip=False), 22)
        self.assertEqual(len(bridge.calls), 1)


if __name__ == "__main__":
    unittest.main()
