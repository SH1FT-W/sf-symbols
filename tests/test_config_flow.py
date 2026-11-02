"""Setup through the UI: confirm, at most one entry; options: symbol browser on/off."""

from __future__ import annotations

from homeassistant.components.frontend import DATA_PANELS
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sf_symbols.const import CONF_SHOW_PANEL, DOMAIN, PANEL_URL_PATH


async def test_user_flow(hass: HomeAssistant, frontend: object) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SF Symbols"
    await hass.async_block_till_done()


async def test_single_instance(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_toggle_panel(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """Turning the symbol browser off removes it from the sidebar at once (entry reloads), on brings it back."""
    assert PANEL_URL_PATH in hass.data[DATA_PANELS]
    result = await hass.config_entries.options.async_init(setup.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SHOW_PANEL: False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert setup.options == {CONF_SHOW_PANEL: False}
    assert PANEL_URL_PATH not in hass.data[DATA_PANELS]
    result = await hass.config_entries.options.async_init(setup.entry_id)
    schema = result["data_schema"].schema
    assert next(k for k in schema if k == CONF_SHOW_PANEL).default() is False
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SHOW_PANEL: True})
    await hass.async_block_till_done()
    assert PANEL_URL_PATH in hass.data[DATA_PANELS]
