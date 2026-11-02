"""Setup: confirm only, at most one entry. Options: show the symbol browser in the sidebar."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
import voluptuous as vol

from .const import CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL, DOMAIN


class SFSymbolsConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry provides the icon sets "sf:" and "ios:"."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SFSymbolsOptionsFlow:
        return SFSymbolsOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="SF Symbols", data={})
        return self.async_show_form(step_id="user")


class SFSymbolsOptionsFlow(OptionsFlowWithReload):
    """Symbol browser on/off; the entry reloads afterwards so the sidebar follows at once."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL)
        schema = vol.Schema({vol.Required(CONF_SHOW_PANEL, default=current): bool})
        return self.async_show_form(step_id="init", data_schema=schema)
