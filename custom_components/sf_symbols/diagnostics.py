"""Diagnostics: symbol set, counts, variants, module URLs, panel, conflict with Cupertino (no personal data)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import SFSymbolsConfigEntry, cupertino_present, module_url
from .const import CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: SFSymbolsConfigEntry) -> dict[str, Any]:
    data = entry.runtime_data
    meta = data.meta
    return {
        "set_version": data.set_version,
        "app_build": meta.get("app_build"),
        "symbols": data.symbol_count,
        "listed_in_picker": meta.get("listed"),
        "aliases": meta.get("aliases"),
        "hierarchical": meta.get("hierarchical"),
        "multicolor": meta.get("multicolor"),
        "missing": meta.get("missing", []),
        "data_hash": meta.get("hash"),
        "module_url": module_url(data),
        "cupertino_installed": cupertino_present(hass),
        "show_panel": entry.options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL),
    }
