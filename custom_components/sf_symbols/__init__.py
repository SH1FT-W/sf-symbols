"""SF Symbols: Apples Symbole als Symbolsätze „sf:“ (Apple-Namen) und „ios:“ (Cupertino-kompatibel).

Die Integration liefert ein Frontend-Modul (öffentlich) und die vorab erzeugten Symboldaten (nur mit Anmeldung)
aus. Alles Weitere (Auflösen der Namen, Ebenen, Suche im Symbol-Picker) passiert im Browser.
"""

from __future__ import annotations

from http import HTTPStatus
import logging

from aiohttp import web
from homeassistant.components.frontend import add_extra_js_url, remove_extra_js_url
from homeassistant.components.http import HomeAssistantView
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
    CUPERTINO_DOMAIN,
    DATA_DIR,
    DOMAIN,
    FRONTEND_FILE,
    ISSUE_CUPERTINO,
    URL_BASE,
)
from .symbols import MODULE_FILE, SymbolData, SymbolDataError, is_data_file, load_symbol_data

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type SFSymbolsConfigEntry = ConfigEntry[SymbolData]


def module_url(data: SymbolData) -> str:
    return f"{URL_BASE}/{data.version}/{MODULE_FILE}"


def _current(hass: HomeAssistant) -> SymbolData | None:
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        data: SymbolData = entry.runtime_data
        return data
    return None


def _cache_header(data: SymbolData, version: str, *, private: bool) -> str:
    """Alte Versionen (Browser-Cache nach einem Update) bekommen den aktuellen Stand, aber ohne Langzeit-Cache."""
    if version != data.version:
        return "no-cache"
    return CACHE_IMMUTABLE_PRIVATE if private else CACHE_IMMUTABLE


async def _read(hass: HomeAssistant, data: SymbolData, path: str) -> bytes | None:
    """Erst im Event-Loop im Speicher-Cache nachsehen, nur beim ersten Abruf die Datei im Executor lesen."""
    cached = data.cached(path)
    if cached is not None:
        return cached
    return await hass.async_add_executor_job(data.load, path)


class SFSymbolsModuleView(HomeAssistantView):
    """Liefert nur das Loader-Modul öffentlich aus (/sf_symbols/<version>/sf-symbols.js).

    Der Browser lädt Zusatzmodule ohne Token; das Modul enthält keine Symbole. Die Daten holt es danach
    mit dem Token des angemeldeten Nutzers über SFSymbolsDataView. Ohne geladenen Eintrag: 404.
    """

    url = f"{URL_BASE}/{{version}}/{MODULE_FILE}"
    name = "api:sf_symbols:module"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, version: str) -> web.StreamResponse:
        data = _current(self.hass)
        if data is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        body = await _read(self.hass, data, MODULE_FILE)
        return web.Response(
            body=body,
            content_type="text/javascript",
            charset="utf-8",
            headers={"Cache-Control": _cache_header(data, version, private=False)},
        )


class SFSymbolsDataView(HomeAssistantView):
    """Symboldaten (index.json, m/xx.json, v/xx.json) nur mit HA-Anmeldung, sonst 401.

    Apples Symbole sollen nicht ohne Login abrufbar sein. Cache: „private“ (nur der Browser des Nutzers),
    ein Jahr, versionierte URL.
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
    # Reihenfolge zählt: das öffentliche Modul vor der allgemeinen Daten-Route anmelden.
    hass.http.register_view(SFSymbolsModuleView(hass))
    hass.http.register_view(SFSymbolsDataView(hass))
    return True


def cupertino_present(hass: HomeAssistant) -> bool:
    """Cupertino-Icons geladen oder eingerichtet? Beide registrieren den Satz „ios:“."""
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

    async_update_conflict_issue(hass)

    # Cupertino kann nach uns laden – nach dem Start noch einmal prüfen.
    @callback
    def _recheck(_hass: HomeAssistant) -> None:
        async_update_conflict_issue(hass)

    entry.async_on_unload(async_at_started(hass, _recheck))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SFSymbolsConfigEntry) -> bool:
    ir.async_delete_issue(hass, DOMAIN, ISSUE_CUPERTINO)
    return True
