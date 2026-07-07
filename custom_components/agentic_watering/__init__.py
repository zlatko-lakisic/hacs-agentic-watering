"""Agentic Watering — HACS distribution for sequential AI irrigation YAML packages."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .plant_knowledge import format_knowledge_block, resolve_water_requirement_mm

__all__ = ["DOMAIN"]

SERVICE_GET_WATER_REQUIREMENT_MM = "get_water_requirement_mm"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Optional("climate_setting", default="temperate_humid"): cv.string,
        vol.Optional("et0_mm_per_week"): vol.Coerce(float),
    }
)


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_GET_WATER_REQUIREMENT_MM):
        return

    async def handle_get_water_requirement_mm(call: ServiceCall) -> dict:
        result = resolve_water_requirement_mm(
            call.data["name"],
            climate_setting=call.data.get("climate_setting"),
            et0_mm_per_week=call.data.get("et0_mm_per_week"),
        )
        block = format_knowledge_block(result)
        return {
            **result,
            "knowledge_block": block,
            "resolved": bool(result.get("found") and block),
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_WATER_REQUIREMENT_MM,
        handle_get_water_requirement_mm,
        schema=SERVICE_SCHEMA,
        supports_response=True,
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services when loaded via configuration.yaml domain block."""
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Register services when loaded via HACS config entry."""
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload integration entry."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_WATER_REQUIREMENT_MM):
        hass.services.async_remove(DOMAIN, SERVICE_GET_WATER_REQUIREMENT_MM)
    return True
