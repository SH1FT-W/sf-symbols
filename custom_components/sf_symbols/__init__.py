"""SF Symbols: Apples Symbole als Symbolsätze „sf:“ (Apple-Namen) und „ios:“ (Cupertino-kompatibel).

Die Integration liefert ein Frontend-Modul und die vorab erzeugten Symboldaten aus. Alles Weitere
(Auflösen der Namen, Ebenen, Suche im Symbol-Picker) passiert im Browser.
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

from .const import CACHE_IMMUTABLE, CUPERTINO_DOMAIN, DATA_DIR, DOMAIN, FRONTEND_FILE, ISSUE_CUPERTINO, URL_BASE
from .symbols import MODULE_FILE, SymbolData, SymbolDataError, load_symbol_data

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type SFSymbolsConfigEntry = ConfigEntry[SymbolData]


def module_url(data: SymbolData) -> str:
    return f"{URL_BASE}/{data.version}/{MODULE_FILE}"


class SFSymbolsView(HomeAssistantView):
    """Liefert Modul und Daten unter /sf_symbols/<version>/<datei>.

    Ohne Anmeldung (wie HAs eigene Frontend-Dateien): das Modul lädt der Browser vor dem Login-Token,
    und es sind nur Symbolformen. Ist kein Eintrag geladen, gibt es 404.
    """

    url = URL_BASE + "/{version}/{path:.+}"
    name = "api:sf_symbols"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    def _current(self) -> SymbolData | None:
        for entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
            data: SymbolData = entry.runtime_data
            return data
        return None

    async def get(self, request: web.Request, version: str, path: str) -> web.StreamResponse:
        data = self._current()
        if data is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        # Alte Versionen (Browser-Cache nach einem Update) bekommen den aktuellen Stand, aber ohne Langzeit-Cache.
        cache = CACHE_IMMUTABLE if version == data.version else "no-cache"
        if path == MODULE_FILE:
            body = await self.hass.async_add_executor_job(data.module_source)
            return web.Response(
                body=body, content_type="text/javascript", charset="utf-8", headers={"Cache-Control": cache}
            )
        payload = await self.hass.async_add_executor_job(data.data_file, path)
        if payload is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        return web.Response(
            body=payload,
            content_type="application/json",
            headers={"Cache-Control": cache, "Content-Encoding": "gzip", "Vary": "Accept-Encoding"},
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.http.register_view(SFSymbolsView(hass))
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
