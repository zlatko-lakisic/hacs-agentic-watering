"""Regression tests for overlay skill packing and mTLS TLS helpers.

Both areas caused live Reach failures that unit tests did not catch:
  * skills authored with an `instructions:` block instead of `content:` were
    sent without a `content` mapping -> engine rejected the session.
  * IP-literal engine URLs whose server cert lists the address only as a
    dNSName SAN failed hostname verification.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "agentic_watering"
sys.path.insert(0, str(INTEGRATION))

from ao_reach.mtls import host_is_ip_literal  # noqa: E402
from ao_reach.overlay_packer import OverlayPacker  # noqa: E402

OVERLAY_ROOT = INTEGRATION / "overlays"


class OverlaySkillPackingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = OverlayPacker().pack(OVERLAY_ROOT)

    def test_every_skill_has_content_body(self) -> None:
        self.assertTrue(self.pack.skills, "no skills packed")
        for skill in self.pack.skills:
            content = skill.get("content")
            self.assertIsInstance(
                content, dict, f"{skill.get('id')} missing content mapping"
            )
            self.assertTrue(
                str(content.get("body") or "").strip(),
                f"{skill.get('id')} has empty content body",
            )
            self.assertNotIn(
                "file", content, f"{skill.get('id')} content.file not resolved to body"
            )

    def test_skills_injected_into_agent_backstory(self) -> None:
        planner = next(
            a for a in self.pack.agents if a["id"].endswith("irrigation_planner")
        )
        self.assertIn("48", planner.get("backstory", ""))  # soil band figure
        self.assertTrue(
            all(str(s).startswith("client.") for s in planner.get("skills", []))
        )


class HostIpLiteralTests(unittest.TestCase):
    def test_ip_literal_endpoints(self) -> None:
        self.assertTrue(host_is_ip_literal("https://172.16.90.20:8765"))
        self.assertTrue(host_is_ip_literal("https://10.0.10.16:8765"))

    def test_hostname_endpoints(self) -> None:
        self.assertFalse(
            host_is_ip_literal("https://omega-jetson-orin.mostardesigns.com:8765")
        )
        self.assertFalse(host_is_ip_literal("https://localhost:8765"))


if __name__ == "__main__":
    unittest.main()
