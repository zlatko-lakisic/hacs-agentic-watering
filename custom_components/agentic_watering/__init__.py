"""Agentic Watering — AO Reach sequential irrigation for Home Assistant."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_API_TOKEN,
    CONF_APP_ID,
    CONF_ENABLE_WEATHER_MCP,
    CONF_ENABLED_AGENTS,
    CONF_ENGINE_URL,
    CONF_ENROLL_TOKEN,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_TTL_SECONDS,
    CONF_USE_REACH,
    DEFAULT_APP_ID,
    DEFAULT_ENABLED_AGENTS,
    DEFAULT_ENGINE_URL,
    DEFAULT_GARDEN_LATITUDE,
    DEFAULT_GARDEN_LONGITUDE,
    DEFAULT_TTL,
    DOMAIN,
    SERVICE_CLEAR_PAIRING,
    SERVICE_PAIR,
    SERVICE_PLAN_ZONE_MINUTES,
    SERVICE_PROBE_REACH,
    SERVICE_REFRESH_OVERLAY,
)
from .minutes_parse import clamp_run_minutes, parse_minutes
from .probe_heuristics import (
    extract_moisture_values,
    probe_skip_recommendation,
    recommends_skip,
    soil_adjustment_guide,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLAN_ZONE_SCHEMA = vol.Schema(
    {
        vol.Optional("zone_label", default=""): cv.string,
        vol.Optional("zone_entity_id", default=""): cv.string,
        vol.Optional("plant_profile", default=""): cv.string,
        vol.Optional("zone_profile_json", default="{}"): cv.string,
        vol.Optional("days_since_last_irrigation", default=0): vol.Coerce(int),
        vol.Optional("last_run_duration_minutes", default=0): vol.Coerce(float),
        vol.Optional("garden_temp_f", default="unknown"): cv.string,
        vol.Optional("garden_temp_peak_f", default="unknown"): cv.string,
        vol.Optional("soil_context_json", default="{}"): cv.string,
        vol.Optional("open_meteo_json", default="{}"): cv.string,
        vol.Optional("forecast_json", default="[]"): cv.string,
        vol.Optional("weather_context_json", default="{}"): cv.string,
        vol.Optional("probe_hint", default=""): cv.string,
        vol.Optional("latitude"): vol.Coerce(float),
        vol.Optional("longitude"): vol.Coerce(float),
        vol.Optional("selected_agents"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("mock_reply"): cv.string,
    }
)

PAIR_SCHEMA = vol.Schema(
    {
        vol.Required("enroll_token"): cv.string,
        vol.Optional("client_name"): cv.string,
    }
)


def _merged_entry_data(entry: ConfigEntry) -> dict[str, Any]:
    return {**entry.data, **entry.options}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up via configuration.yaml when present."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up via HACS / UI config entry."""
    from .mcp_bootstrap import WateringMcpBootstrap
    from .pairing import AoPairingService
    from .reach_session import WateringReachSession

    hass.data.setdefault(DOMAIN, {})
    data = _merged_entry_data(entry)
    overlay_root = Path(__file__).parent / "overlays"
    use_reach = bool(data.get(CONF_USE_REACH, True))
    enable_weather = bool(data.get(CONF_ENABLE_WEATHER_MCP, True))
    enabled_agents = list(data.get(CONF_ENABLED_AGENTS) or DEFAULT_ENABLED_AGENTS)
    engine_url = str(data.get(CONF_ENGINE_URL) or DEFAULT_ENGINE_URL)

    material_dir = Path(hass.config.path(f"agentic_watering_mtls_{entry.entry_id}"))
    pairing = await hass.async_add_executor_job(
        lambda: AoPairingService(engine_url=engine_url, material_dir=material_dir)
    )

    session: WateringReachSession | None = None
    if use_reach:
        session = WateringReachSession(
            engine_url=engine_url,
            app_id=str(data.get(CONF_APP_ID) or DEFAULT_APP_ID),
            api_token=(str(data.get(CONF_API_TOKEN) or "").strip() or None),
            ttl_seconds=int(data.get(CONF_TTL_SECONDS) or DEFAULT_TTL),
            overlay_root=overlay_root,
            enabled_agents=enabled_agents,
            enable_weather_mcp=enable_weather,
            bootstrap=WateringMcpBootstrap(
                overlay_root=overlay_root, enable_weather=enable_weather
            ),
            pairing=pairing,
        )

    runtime = {
        "entry": entry,
        "session": session,
        "pairing": pairing,
        "overlay_root": overlay_root,
        "enabled_agents": enabled_agents,
        "latitude": float(data.get(CONF_LATITUDE, DEFAULT_GARDEN_LATITUDE)),
        "longitude": float(data.get(CONF_LONGITUDE, DEFAULT_GARDEN_LONGITUDE)),
        "use_reach": use_reach,
    }
    hass.data[DOMAIN][entry.entry_id] = runtime
    hass.data[DOMAIN]["primary"] = runtime

    enroll_token = str(data.get(CONF_ENROLL_TOKEN) or "").strip()
    if enroll_token:
        result = await pairing.enroll(enroll_token)
        if not result.get("ok"):
            _LOGGER.error("AO mTLS enrollment failed: %s", result.get("error"))
        hass.config_entries.async_update_entry(
            entry,
            data={k: v for k, v in entry.data.items() if k != CONF_ENROLL_TOKEN},
            options={k: v for k, v in entry.options.items() if k != CONF_ENROLL_TOKEN},
        )

    async def _plan_zone_minutes(call: ServiceCall) -> dict[str, Any]:
        return await _async_plan_zone_minutes(hass, call)

    async def _probe_reach(call: ServiceCall) -> dict[str, Any]:
        rt = hass.data[DOMAIN].get("primary") or {}
        sess: WateringReachSession | None = rt.get("session")
        pair_svc = rt.get("pairing")
        pairing_info = pair_svc.inspect() if pair_svc else {"paired": False}
        if sess is None:
            return {
                "ok": False,
                "error": "Reach disabled or not configured",
                "pairing": pairing_info,
            }
        try:
            await sess.ensure_started()
            st = sess.state
            return {
                "ok": True,
                "connected": sess.connected,
                "paired": sess.paired,
                "pairing": pairing_info,
                "session_overlay": bool(getattr(sess.bridge, "session_overlay", False)),
                "mcp_tunnel": bool(getattr(sess.bridge, "mcp_tunnel", False)),
                "state": getattr(st, "name", str(st)),
                "enabled_agents": list(sess.enabled_agents),
                "engine_url": sess.engine_url,
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "pairing": pairing_info}

    async def _pair(call: ServiceCall) -> dict[str, Any]:
        rt = hass.data[DOMAIN].get("primary") or {}
        pair_svc = rt.get("pairing")
        if pair_svc is None:
            return {"ok": False, "error": "Pairing service unavailable"}
        result = await pair_svc.enroll(
            str(call.data["enroll_token"]).strip(),
            client_name=call.data.get("client_name"),
        )
        sess = rt.get("session")
        if result.get("ok") and sess is not None:
            await sess.stop()
        hass.bus.async_fire(f"{DOMAIN}_pair_result", result)
        return result

    async def _clear_pairing(call: ServiceCall) -> dict[str, Any]:
        rt = hass.data[DOMAIN].get("primary") or {}
        pair_svc = rt.get("pairing")
        if pair_svc is None:
            return {"ok": False, "error": "Pairing service unavailable"}
        sess = rt.get("session")
        if sess is not None:
            await sess.stop()
        return await hass.async_add_executor_job(pair_svc.clear)

    async def _refresh_overlay(call: ServiceCall) -> None:
        rt = hass.data[DOMAIN].get("primary") or {}
        sess = rt.get("session")
        if sess is not None:
            await sess.refresh_overlay()

    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAN_ZONE_MINUTES,
        _plan_zone_minutes,
        schema=PLAN_ZONE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PROBE_REACH,
        _probe_reach,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_OVERLAY,
        _refresh_overlay,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PAIR,
        _pair,
        schema=PAIR_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_PAIRING,
        _clear_pairing,
        supports_response=SupportsResponse.OPTIONAL,
    )

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate empty v1 entries to Reach-capable defaults."""
    if entry.version < 2:
        data = {
            CONF_ENGINE_URL: DEFAULT_ENGINE_URL,
            CONF_API_TOKEN: "",
            CONF_APP_ID: DEFAULT_APP_ID,
            CONF_TTL_SECONDS: DEFAULT_TTL,
            CONF_USE_REACH: True,
            CONF_ENABLE_WEATHER_MCP: True,
            CONF_ENABLED_AGENTS: list(DEFAULT_ENABLED_AGENTS),
            CONF_LATITUDE: DEFAULT_GARDEN_LATITUDE,
            CONF_LONGITUDE: DEFAULT_GARDEN_LONGITUDE,
            **dict(entry.data),
        }
        hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload integration entry."""
    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime and runtime.get("session"):
        await runtime["session"].stop()
    if hass.data.get(DOMAIN, {}).get("primary") is runtime:
        hass.data[DOMAIN].pop("primary", None)
    if DOMAIN in hass.data and not any(
        k != "primary" for k in hass.data[DOMAIN]
    ):
        hass.services.async_remove(DOMAIN, SERVICE_PLAN_ZONE_MINUTES)
        hass.services.async_remove(DOMAIN, SERVICE_PROBE_REACH)
        hass.services.async_remove(DOMAIN, SERVICE_REFRESH_OVERLAY)
        hass.services.async_remove(DOMAIN, SERVICE_PAIR)
        hass.services.async_remove(DOMAIN, SERVICE_CLEAR_PAIRING)
    return True


def _build_zone_prompt(
    *,
    call_data: dict[str, Any],
    latitude: float,
    longitude: float,
) -> str:
    plant = str(call_data.get("plant_profile") or "")
    soil_raw = call_data.get("soil_context_json") or "{}"
    try:
        soil = json.loads(soil_raw) if isinstance(soil_raw, str) else (soil_raw or {})
    except json.JSONDecodeError:
        soil = {"has_soil_probe": False, "raw": soil_raw}
    if isinstance(soil, dict) and soil.get("has_soil_probe"):
        soil = {
            **soil,
            "adjustment_guide": soil_adjustment_guide(plant),
            "plant_profile": plant or soil.get("plant_profile"),
        }
    probe_hint = str(call_data.get("probe_hint") or "")
    if not probe_hint and isinstance(soil, dict):
        vals = extract_moisture_values(soil)
        if vals:
            probe_hint = probe_skip_recommendation(
                plant_profile=plant, moisture_values=vals
            )

    lines = [
        f"Zone label: {call_data.get('zone_label') or 'unknown zone'}",
        f"Zone entity: {call_data.get('zone_entity_id') or 'unknown'}",
        f"Garden coordinates: {latitude}, {longitude}",
        "",
        f"Zone profile: {call_data.get('zone_profile_json') or '{}'}",
        "",
        f"Days since last irrigation: {call_data.get('days_since_last_irrigation', 0)}",
        f"Last run duration (minutes): {call_data.get('last_run_duration_minutes', 0)}",
        "",
        f"Garden temperature now (F): {call_data.get('garden_temp_f', 'unknown')}",
        f"Garden temperature 24h peak (F): {call_data.get('garden_temp_peak_f', 'unknown')}",
    ]
    if probe_hint:
        lines.append(f"Heuristic probe hint: {probe_hint}")
    lines.extend(
        [
            f"Soil moisture context: {json.dumps(soil)}",
            f"Open-Meteo past 72h precipitation (HA fallback): {call_data.get('open_meteo_json') or '{}'}",
            f"AccuWeather context: {call_data.get('weather_context_json') or '{}'}",
            f"OpenWeatherMap forecast (next ~24h): {call_data.get('forecast_json') or '[]'}",
            "",
            "Use weather-mcp tools when available for this lat/lon before finalizing minutes.",
            "End with MINUTES: <0-25>.",
        ]
    )
    return "\n".join(lines)


async def _async_plan_zone_minutes(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, Any]:
    rt = hass.data.get(DOMAIN, {}).get("primary") or {}
    sess = rt.get("session")
    lat = float(call.data.get("latitude") or rt.get("latitude") or DEFAULT_GARDEN_LATITUDE)
    lon = float(
        call.data.get("longitude") or rt.get("longitude") or DEFAULT_GARDEN_LONGITUDE
    )
    plant = str(call.data.get("plant_profile") or "")
    soil_raw = call.data.get("soil_context_json") or "{}"
    try:
        soil = json.loads(soil_raw) if isinstance(soil_raw, str) else {}
    except json.JSONDecodeError:
        soil = {}
    vals = extract_moisture_values(soil if isinstance(soil, dict) else {})
    probe_hint = str(call.data.get("probe_hint") or "")
    if not probe_hint and vals:
        probe_hint = probe_skip_recommendation(plant_profile=plant, moisture_values=vals)
    probe_skip = recommends_skip(probe_hint)

    mock_reply = call.data.get("mock_reply")
    agents = list(call.data.get("selected_agents") or rt.get("enabled_agents") or [])

    if mock_reply is not None:
        raw = str(mock_reply)
        question_id = "mock"
        agents_used = agents
    elif sess is None:
        return {
            "minutes": 0,
            "run_minutes": 0,
            "parsed": False,
            "probe_skip": probe_skip,
            "probe_hint": probe_hint,
            "raw_text": "reach_disabled",
            "question_id": "",
            "agents_used": [],
            "error": "Reach session not configured",
        }
    else:
        text = _build_zone_prompt(call_data=dict(call.data), latitude=lat, longitude=lon)
        try:
            result = await sess.chat_zone(
                text=text, selected_agent_provider_ids=agents or None
            )
            raw = str(result.get("text") or "")
            question_id = str(result.get("questionId") or result.get("question_id") or "")
            agents_used = agents
        except Exception as exc:  # noqa: BLE001
            _LOGGER.exception("plan_zone_minutes Reach chat failed: %s", exc)
            return {
                "minutes": 0,
                "run_minutes": 0,
                "parsed": False,
                "probe_skip": probe_skip,
                "probe_hint": probe_hint,
                "raw_text": "",
                "question_id": "",
                "agents_used": agents,
                "error": str(exc),
            }

    parsed, minutes = parse_minutes(raw)
    run_minutes = clamp_run_minutes(minutes, parsed=parsed, probe_skip=probe_skip)
    return {
        "minutes": minutes,
        "run_minutes": run_minutes,
        "parsed": parsed,
        "probe_skip": probe_skip,
        "probe_hint": probe_hint,
        "raw_text": raw,
        "question_id": question_id,
        "agents_used": agents_used,
        "error": "",
    }
