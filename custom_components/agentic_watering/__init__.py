"""Agentic Watering — HACS distribution for sequential AI irrigation YAML packages."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

__all__ = ["DOMAIN"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration; YAML packages are loaded via configuration.yaml includes."""
    return True
