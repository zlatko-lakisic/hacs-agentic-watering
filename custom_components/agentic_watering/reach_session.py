"""AO Reach session manager for Agentic Watering."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .ao_reach.connection_config import ReachConnectionConfig
from .ao_reach.session_bridge import SessionBridge, SessionBridgeState
from .const import DEFAULT_APP_ID, DEFAULT_ENABLED_AGENTS
from .mcp_bootstrap import WateringMcpBootstrap
from .pairing import AoPairingService

_LOGGER = logging.getLogger(__name__)


class WateringReachSession:
    """Long-lived Reach bridge for irrigation zone planning."""

    def __init__(
        self,
        *,
        engine_url: str,
        app_id: str = DEFAULT_APP_ID,
        api_token: str | None = None,
        ttl_seconds: int = 3600,
        overlay_root: Path,
        enabled_agents: list[str] | None = None,
        enable_weather_mcp: bool = True,
        bootstrap: WateringMcpBootstrap | None = None,
        pairing: AoPairingService | None = None,
    ) -> None:
        self.engine_url = engine_url
        self.app_id = app_id
        self.api_token = api_token
        self.ttl_seconds = ttl_seconds
        self.overlay_root = overlay_root
        self.enabled_agents = list(enabled_agents or DEFAULT_ENABLED_AGENTS)
        self.enable_weather_mcp = enable_weather_mcp
        self.pairing = pairing
        self.bootstrap = bootstrap or WateringMcpBootstrap(
            overlay_root=overlay_root, enable_weather=enable_weather_mcp
        )
        self.bridge = SessionBridge()
        self.connected = False
        self.last_error: str | None = None

    def _config(self, *, session_id: str = "watering") -> ReachConnectionConfig:
        headers: dict[str, str] = {
            "x-agentic-user-name": "home-assistant",
            "x-agentic-session-id": session_id,
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return ReachConnectionConfig(
            base_url=self.engine_url,
            app_id=self.app_id,
            headers=headers,
            ttl_seconds=self.ttl_seconds,
            question_id_prefix="agentic-watering",
            dynamic_planning=True,
            default_run_mode="dynamic",
            mtls=self.pairing.mtls_config() if self.pairing else None,
        )

    @property
    def paired(self) -> bool:
        return bool(self.pairing and self.pairing.mtls_config() is not None)

    async def ensure_started(self, *, session_id: str = "watering") -> None:
        if self.bridge.is_active:
            return
        if not self.paired and self.engine_url.lower().startswith("https://"):
            _LOGGER.warning(
                "Starting Reach without mTLS material; engines with mtls.required "
                "will reject this session. Run agentic_watering.pair first."
            )
        try:
            await self.bridge.start(
                config=self._config(session_id=session_id),
                overlay_root=str(self.overlay_root),
                mcp_bootstrap=self.bootstrap,
            )
            self.connected = self.bridge.is_active
            self.last_error = None
        except Exception as exc:  # noqa: BLE001
            self.connected = False
            self.last_error = str(exc)
            _LOGGER.exception("Reach session start failed: %s", exc)
            raise

    async def stop(self) -> None:
        await self.bridge.stop(clear_remote=True)
        self.connected = False

    async def refresh_overlay(self) -> None:
        if self.bridge.is_active:
            await self.bridge.refresh_overlay()

    async def chat_zone(
        self,
        *,
        text: str,
        selected_agent_provider_ids: list[str] | None = None,
        timeout: float = 600.0,
    ) -> dict[str, Any]:
        await self.ensure_started()
        agents = [
            a
            for a in (selected_agent_provider_ids or self.enabled_agents)
            if a and str(a).strip()
        ]
        if not agents:
            raise RuntimeError("No irrigation agents selected — fail-closed")
        return await self.bridge.chat(
            text=text,
            run_mode="dynamic",
            selected_agent_provider_ids=agents,
            timeout=timeout,
        )

    @property
    def state(self) -> SessionBridgeState:
        return self.bridge.state

    @property
    def session_overlay_active(self) -> bool:
        return bool(getattr(self.bridge, "session_overlay", False) or self.bridge.is_active)
