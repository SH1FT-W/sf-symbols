"""SF Symbols: Apple's symbols as icon sets "sf:" (Apple names) and "ios:" (Cupertino compatible).

The integration serves a frontend module (public) and the pre-generated symbol data (login only). Everything
else (resolving names, layers, search in the icon picker) happens in the browser. Optionally a symbol browser
in the sidebar (admins only).
"""

from __future__ import annotations

from http import HTTPStatus
import logging

from aiohttp import web
from homeassistant.components.frontend import (
    add_extra_js_url,
    async_panel_exists,
    async_remove_panel,
    remove_extra_js_url,
)
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import (
    CACHE_IMMUTABLE,
    CACHE_IMMUTABLE_PRIVATE,
    CONF_SHOW_PANEL,
    CUPERTINO_DOMAIN,
    DATA_DIR,
    DEFAULT_SHOW_PANEL,
    DOMAIN,
    FRONTEND_FILE,
    ISSUE_CUPERTINO,
    PANEL_ELEMENT,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    URL_BASE,
)
from .symbols import MODULE_FILE, PANEL_FILE, SymbolData, SymbolDataError, is_data_file, load_symbol_data

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type SFSymbolsConfigEntry = ConfigEntry[SymbolData]


def module_url(data: SymbolData) -> str:
    return f"{URL_BASE}/{data.version}/{MODULE_FILE}"


def panel_url(data: SymbolData) -> str:
    return f"{URL_BASE}/{data.version}/{PANEL_FILE}"


def _current(hass: HomeAssistant) -> SymbolData | None:
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        data: SymbolData = entry.runtime_data
        return data
    return None


def _cache_header(data: SymbolData, version: str, *, private: bool) -> str:
    """Old versions (browser cache after an update) get the current content, but without long-term caching."""
    if version != data.version:
        return "no-cache"
    return CACHE_IMMUTABLE_PRIVATE if private else CACHE_IMMUTABLE


async def _read(hass: HomeAssistant, data: SymbolData, path: str) -> bytes | None:
    """Look in the memory cache within the event loop first, read the file in the executor only once."""
    cached = data.cached(path)
    if cached is not None:
        return cached
    return await hass.async_add_executor_job(data.load, path)


class SFSymbolsModuleView(HomeAssistantView):
    """Serves only the loader and panel modules publicly (/sf_symbols/<version>/sf-symbols[-panel].js).

    The browser loads extra modules without a token; the modules contain no symbols. The data is fetched
    afterwards with the logged-in user's token through SFSymbolsDataView. Without a loaded entry: 404.
    """

    url = URL_BASE + r"/{version}/{file:sf-symbols(?:-panel)?\.js}"
    name = "api:sf_symbols:module"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, version: str, file: str) -> web.StreamResponse:
        data = _current(self.hass)
        if data is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        body = await _read(self.hass, data, file)
        return web.Response(
            body=body,
            content_type="text/javascript",
            charset="utf-8",
            headers={"Cache-Control": _cache_header(data, version, private=False)},
        )


class SFSymbolsDataView(HomeAssistantView):
    """Symbol data (index.json, variants.json, m/xx.json, v/xx.json) only with an HA login, otherwise 401.

    Apple's symbols must not be reachable without a login. Cache: "private" (only the user's browser),
    one year, versioned URL.
    """

    url = URL_BASE + "/{version}/{path:.+}"
    name = "api:sf_symbols:data"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, version: str, path: str) -> web.StreamResponse:
        data = _current(self.hass)
        if data is None or not is_data_file(path):
            return web.Response(status=HTTPStatus.NOT_FOUND)
        payload = await _read(self.hass, data, path)
        if payload is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        return web.Response(
            body=payload,
            content_type="application/json",
            headers={
                "Cache-Control": _cache_header(data, version, private=True),
                "Content-Encoding": "gzip",
                "Vary": "Accept-Encoding",
            },
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    # Order matters: register the public modules before the general data route.
    hass.http.register_view(SFSymbolsModuleView(hass))
    hass.http.register_view(SFSymbolsDataView(hass))
    return True


def cupertino_present(hass: HomeAssistant) -> bool:
    """Cupertino Icons loaded or set up? Both register the icon set "ios:"."""
    return CUPERTINO_DOMAIN in hass.config.components or bool(hass.config_entries.async_entries(CUPERTINO_DOMAIN))


@callback
def async_update_conflict_issue(hass: HomeAssistant) -> None:
    if cupertino_present(hass):
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_CUPERTINO,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_CUPERTINO,
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_CUPERTINO)


async def async_setup_entry(hass: HomeAssistant, entry: SFSymbolsConfigEntry) -> bool:
    integration = await async_get_integration(hass, DOMAIN)
    try:
        data = await hass.async_add_executor_job(
            load_symbol_data, DATA_DIR, FRONTEND_FILE, str(integration.version or "0")
        )
    except SymbolDataError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="data_missing", translation_placeholders={"error": str(err)}
        ) from err
    entry.runtime_data = data
    url = module_url(data)
    add_extra_js_url(hass, url)
    entry.async_on_unload(lambda: remove_extra_js_url(hass, url))
    _LOGGER.debug("SF Symbols %s: %s symbols at %s", data.set_version, data.symbol_count, url)

    show_panel = entry.options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL)
    if show_panel and async_panel_exists(hass, PANEL_URL_PATH):
        # e.g. a dashboard with the same URL: keep the icons working, just no browser
        _LOGGER.warning("SF Symbols: sidebar path /%s is already in use, symbol browser not added", PANEL_URL_PATH)
    elif show_panel:
        await async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name=PANEL_ELEMENT,
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            module_url=panel_url(data),
            require_admin=True,
        )
        entry.async_on_unload(lambda: async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False))

    async_update_conflict_issue(hass)

    # Cupertino may load after us: check again once Home Assistant has started.
    @callback
    def _recheck(_hass: HomeAssistant) -> None:
        async_update_conflict_issue(hass)

    entry.async_on_unload(async_at_started(hass, _recheck))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SFSymbolsConfigEntry) -> bool:
    ir.async_delete_issue(hass, DOMAIN, ISSUE_CUPERTINO)
    return True
