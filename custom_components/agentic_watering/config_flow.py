"""Config flow for Agentic Watering service integration."""

from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN


class AgenticWateringConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Agentic Watering."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Create a single config entry with no required settings."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="Agentic Watering", data={})
