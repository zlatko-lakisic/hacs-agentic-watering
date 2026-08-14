"""Live AO Reach smoke test for Agentic Watering.

Connects to the AO engine with the same vendored ao_reach client the Home
Assistant integration uses, registers the watering overlay, and asks for
minutes on one zone. Reports pairing / sessionOverlay / mcpTunnel state so
deployment problems are distinguishable from LLM problems.

Usage:
  python scripts/live_reach_test.py --from-ha-config \\\\host\\config
  python scripts/live_reach_test.py --engine-url https://host:8765 --token ao_xxx
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

INTEGRATION_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "agentic_watering"
sys.path.insert(0, str(INTEGRATION_DIR))

import yaml  # noqa: E402

from ao_reach.connection_config import ReachConnectionConfig  # noqa: E402
from ao_reach.ids import bare_agent_id, to_client_agent_id  # noqa: E402
from ao_reach.local_mcp_host import LocalMcpHost  # noqa: E402
from ao_reach.mcp_bootstrap import (  # noqa: E402
    SessionMcpBootstrap,
    SessionMcpBootstrapResult,
)
from ao_reach.mcp_session_spec import session_tunnel_mcp_entry  # noqa: E402
from ao_reach.mtls import (  # noqa: E402
    ReachMtlsConfig,
    host_is_ip_literal,
    material_present,
)
from ao_reach.session_bridge import SessionBridge  # noqa: E402


class _WeatherOnlyBootstrap(SessionMcpBootstrap):
    """Minimal standalone mirror of WateringMcpBootstrap for weather_mcp only."""

    def __init__(self, overlay_root: Path) -> None:
        self.overlay_root = overlay_root

    async def prepare(
        self, host: LocalMcpHost, *, mcp_tunnel: bool
    ) -> SessionMcpBootstrapResult:
        if not mcp_tunnel:
            return SessionMcpBootstrapResult(warnings=["mcp tunnel disabled on engine"])
        path = self.overlay_root / "mcp_providers" / "weather_mcp.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        bare = bare_agent_id(str(raw.get("id") or "weather_mcp"))
        alias = str(raw.get("alias") or bare)
        env = {str(k): str(v) for k, v in (raw.get("env") or {}).items()}
        await host.start_npx_package(
            alias=alias, package=str(raw["npx_package"]), extra_env=env
        )
        return SessionMcpBootstrapResult(
            mcps=[
                session_tunnel_mcp_entry(
                    client_id=to_client_agent_id(bare),
                    description=str(raw.get("description") or bare),
                    alias=alias,
                )
            ],
            active_tunnel_bare_ids=[bare],
        )
from minutes_parse import clamp_run_minutes, parse_minutes  # noqa: E402
from probe_heuristics import (  # noqa: E402
    probe_skip_recommendation,
    recommends_skip,
    soil_adjustment_guide,
)

DEFAULT_ZONE = {
    "zone_label": "Zucchini",
    "zone_entity_id": "switch.zucchini_zone",
    "plant_profile": "zucchini",
    "area_sqm": 6.0,
    "estimated_flow_gpm": 0.35,
    "moisture_values": [21.0, 27.0, 31.0],
    "days_since_last_irrigation": 3,
    "last_run_duration_minutes": 0,
    "temp_f": "86",
    "temp_peak_f": "91",
}


def load_ha_entry(config_root: str) -> tuple[dict, str]:
    path = Path(config_root) / ".storage" / "core.config_entries"
    raw = json.loads(path.read_text(encoding="utf-8"))
    for entry in raw["data"]["entries"]:
        if entry.get("domain") == "agentic_watering":
            merged = {**(entry.get("data") or {}), **(entry.get("options") or {})}
            return merged, entry["entry_id"]
    raise SystemExit("No agentic_watering config entry found in HA .storage")


def build_prompt(zone: dict, *, latitude: float, longitude: float) -> tuple[str, str]:
    plant = zone["plant_profile"]
    values = list(zone["moisture_values"])
    hint = probe_skip_recommendation(plant_profile=plant, moisture_values=values)
    soil = {
        "has_soil_probe": True,
        "plant_profile": plant,
        "driest_percent": min(values),
        "wettest_percent": max(values),
        "values": values,
        "adjustment_guide": soil_adjustment_guide(plant),
    }
    profile = {
        "plant_profile": plant,
        "area_sqm": zone["area_sqm"],
        "estimated_flow_gpm": zone["estimated_flow_gpm"],
    }
    text = "\n".join(
        [
            f"Zone label: {zone['zone_label']}",
            f"Zone entity: {zone['zone_entity_id']}",
            f"Garden coordinates: {latitude}, {longitude}",
            "",
            f"Zone profile: {json.dumps(profile)}",
            "",
            f"Days since last irrigation: {zone['days_since_last_irrigation']}",
            f"Last run duration (minutes): {zone['last_run_duration_minutes']}",
            "",
            f"Garden temperature now (F): {zone['temp_f']}",
            f"Garden temperature 24h peak (F): {zone['temp_peak_f']}",
            f"Heuristic probe hint: {hint}",
            f"Soil moisture context: {json.dumps(soil)}",
            "",
            "Use weather-mcp tools when available for this lat/lon before finalizing minutes.",
            "End with MINUTES: <0-25>.",
        ]
    )
    return text, hint


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-ha-config", dest="ha_config")
    ap.add_argument("--engine-url")
    ap.add_argument("--token")
    ap.add_argument("--app-id", default="agentic-watering")
    ap.add_argument("--material-dir")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument(
        "--weather-mcp",
        action="store_true",
        help=(
            "Start the weather-mcp tunnel via a local npx proxy. Works on Linux "
            "(HA OS/Container); the mcp-proxy child spawn is known to fail on "
            "native Windows, so validate this path on the HA host itself."
        ),
    )
    ap.add_argument(
        "--agents",
        default="client.irrigation_planner,client.irrigation_zone_specialist",
    )
    args = ap.parse_args()

    latitude, longitude = 41.0137572, -73.8082339
    engine_url, token, material_dir = args.engine_url, args.token, args.material_dir

    if args.ha_config:
        data, entry_id = load_ha_entry(args.ha_config)
        engine_url = engine_url or data.get("engine_url")
        token = token or data.get("api_token")
        latitude = float(data.get("latitude", latitude))
        longitude = float(data.get("longitude", longitude))
        if not material_dir:
            candidate = Path(args.ha_config) / f"agentic_watering_mtls_{entry_id}"
            material_dir = str(candidate)
        print(f"HA entry: {entry_id}")

    if not engine_url:
        raise SystemExit("--engine-url or --from-ha-config required")

    paired = bool(material_dir and material_present(str(material_dir)))
    print(f"engine_url      : {engine_url}")
    print(f"app_id          : {args.app_id}")
    print(f"api_token       : {'set' if token else 'MISSING'}")
    print(f"material_dir    : {material_dir}")
    print(f"mtls paired     : {paired}")
    print(f"ip endpoint     : {host_is_ip_literal(engine_url)} (hostname verify relaxed if True)")

    headers = {
        "x-agentic-user-name": "home-assistant",
        "x-agentic-session-id": "watering-livetest",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    config = ReachConnectionConfig(
        base_url=engine_url,
        app_id=args.app_id,
        headers=headers,
        ttl_seconds=3600,
        question_id_prefix="agentic-watering-livetest",
        dynamic_planning=True,
        default_run_mode="dynamic",
        mtls=ReachMtlsConfig(material_dir=str(material_dir)) if paired else None,
    )

    overlay_root = INTEGRATION_DIR / "overlays"
    bridge = SessionBridge()
    bootstrap = None
    if args.weather_mcp:
        bootstrap = _WeatherOnlyBootstrap(overlay_root)
    label = "with weather-mcp tunnel" if bootstrap else "no local MCP tunnel"
    print(f"\n-- connecting (overlay register, {label}) --")
    try:
        await bridge.start(
            config=config, overlay_root=str(overlay_root), mcp_bootstrap=bootstrap
        )
    except Exception as exc:  # noqa: BLE001
        print(f"CONNECT FAILED: {type(exc).__name__}: {exc}")
        return 2

    print(f"state           : {bridge.state}")
    print(f"sessionOverlay  : {bridge.session_overlay}")
    print(f"mcpTunnel       : {bridge.mcp_tunnel}")
    print(f"agents          : {bridge.registered_agent_ids}")
    print(f"mcps            : {bridge.registered_mcp_ids}")
    if bridge.client_mcp_warnings:
        print(f"mcp warnings    : {bridge.client_mcp_warnings}")

    text, hint = build_prompt(DEFAULT_ZONE, latitude=latitude, longitude=longitude)
    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    print(f"\nprobe hint      : {hint}")
    print(f"-- chat ({DEFAULT_ZONE['zone_label']}, agents={agents}) --")

    rc = 0
    try:
        result = await bridge.chat(
            text=text,
            run_mode="dynamic",
            selected_agent_provider_ids=agents,
            timeout=args.timeout,
        )
        raw = str(result.get("text") or "")
        print(f"\n--- reply ---\n{raw}\n-------------")
        parsed, minutes = parse_minutes(raw)
        run_minutes = clamp_run_minutes(
            minutes, parsed=parsed, probe_skip=recommends_skip(hint)
        )
        print(f"parsed MINUTES  : {parsed} -> {minutes}")
        print(f"run_minutes     : {run_minutes}")
        if not parsed:
            print("FAIL: reply had no MINUTES: line")
            rc = 3
    except Exception as exc:  # noqa: BLE001
        print(f"CHAT FAILED: {type(exc).__name__}: {exc}")
        rc = 4
    finally:
        await bridge.stop(clear_remote=True)

    return rc


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
