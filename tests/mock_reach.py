"""Mock AO Reach SessionBridge.chat for offline unit tests."""

from __future__ import annotations

from typing import Any


class MockSessionBridge:
    def __init__(self, reply_text: str = "MINUTES: 0") -> None:
        self.reply_text = reply_text
        self.is_active = False
        self.session_overlay = True
        self.mcp_tunnel = True
        self.calls: list[dict[str, Any]] = []

    async def start(self, **kwargs: Any) -> None:
        self.is_active = True

    async def stop(self, clear_remote: bool = True) -> None:
        self.is_active = False

    async def chat(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "text": self.reply_text,
            "questionId": "mock-qid-1",
        }

    async def refresh_overlay(self) -> None:
        return None
