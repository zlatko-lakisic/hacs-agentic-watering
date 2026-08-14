"""Weather MCP tunnel bootstrap for Agentic Watering Reach sessions."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .ao_reach.ids import bare_agent_id, to_client_agent_id
from .ao_reach.local_mcp_host import LocalMcpHost
from .ao_reach.mcp_bootstrap import SessionMcpBootstrapResult
from .ao_reach.mcp_session_spec import session_tunnel_mcp_entry
from .const import MCP_WEATHER

_LOGGER = logging.getLogger(__name__)


class WateringMcpBootstrap:
    """Start enabled tunnel MCPs from overlay mcp_providers/."""

    def __init__(
        self,
        *,
        overlay_root: Path,
        enable_weather: bool = True,
        env: dict[str, str] | None = None,
    ) -> None:
        self.overlay_root = overlay_root
        self.enable_weather = enable_weather
        self.env = env or dict(os.environ)

    def _enabled_for(self, bare_id: str) -> bool:
        b = bare_agent_id(bare_id)
        if b == MCP_WEATHER or "weather" in b:
            return self.enable_weather
        return False

    async def prepare(self, host: LocalMcpHost, *, mcp_tunnel: bool) -> SessionMcpBootstrapResult:
        warnings: list[str] = []
        mcps: list[dict[str, Any]] = []
        active: list[str] = []
        if not mcp_tunnel:
            return SessionMcpBootstrapResult(warnings=["mcp tunnel disabled on engine"])

        mcp_dir = self.overlay_root / "mcp_providers"
        if not mcp_dir.is_dir():
            return SessionMcpBootstrapResult()

        for path in sorted(list(mcp_dir.glob("*.yaml")) + list(mcp_dir.glob("*.yml"))):
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                continue
            bare = bare_agent_id(str(raw.get("id") or path.stem))
            if not self._enabled_for(bare):
                continue
            transport = str(raw.get("transport") or "").lower()
            alias = str(raw.get("alias") or bare)
            client_id = to_client_agent_id(bare)
            desc = str(raw.get("description") or bare)
            try:
                extra_env = self._resolve_env(raw.get("env_from") or raw.get("env") or {})
                if transport in ("stdio_tunnel", "stdio", "") or raw.get("npx_package"):
                    pkg = raw.get("npx_package")
                    command = raw.get("command")
                    if pkg:
                        await host.start_npx_package(
                            alias=alias, package=str(pkg), extra_env=extra_env
                        )
                    elif isinstance(command, list) and command:
                        await host.start_stdio_command(
                            alias=alias,
                            command=[str(c) for c in command],
                            extra_env=extra_env,
                        )
                    else:
                        warnings.append(f"mcp {bare}: no npx_package/command")
                        continue
                    mcps.append(
                        session_tunnel_mcp_entry(
                            client_id=client_id, description=desc, alias=alias
                        )
                    )
                    active.append(bare)
                else:
                    warnings.append(f"mcp {bare}: unsupported transport {transport}")
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning("Failed to start tunnel MCP %s: %s", bare, exc)
                warnings.append(f"mcp {bare}: {exc}")

        return SessionMcpBootstrapResult(
            mcps=mcps, warnings=warnings, active_tunnel_bare_ids=active
        )

    def _resolve_env(self, spec: object) -> dict[str, str]:
        out: dict[str, str] = {}
        if isinstance(spec, dict):
            for key, val in spec.items():
                if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                    env_key = val[2:-1]
                    if env_key in self.env:
                        out[str(key)] = self.env[env_key]
                elif isinstance(val, str):
                    out[str(key)] = val
        elif isinstance(spec, list):
            for key in spec:
                k = str(key)
                if k in self.env:
                    out[k] = self.env[k]
        return out
