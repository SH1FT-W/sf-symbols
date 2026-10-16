"""Fixtures: eigene Integrationen erlauben, HTTP + Frontend-Stub (ohne hass_frontend-Paket), Eintrag."""

from __future__ import annotations

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sf_symbols.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    return


@pytest.fixture
async def frontend(hass: HomeAssistant) -> UrlManager:
    """HTTP echt, Frontend nur als URL-Liste (das Frontend-Paket fehlt in der Test-venv)."""
    assert await async_setup_component(hass, "http", {})
    hass.config.components.add("frontend")
    manager = UrlManager(lambda _action, _url: None, [])
    hass.data[DATA_EXTRA_MODULE_URL] = manager
    return manager


@pytest.fixture
async def setup(hass: HomeAssistant, frontend: UrlManager) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="SF Symbols", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
