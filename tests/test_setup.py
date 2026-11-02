"""Setup, serving modules and data, symbol browser panel, conflict with Cupertino, diagnostics, removal."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from unittest.mock import patch

from aiohttp.test_utils import make_mocked_request
from homeassistant.components.frontend import DATA_PANELS, UrlManager, async_register_built_in_panel
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.sf_symbols import SFSymbolsDataView, module_url, panel_url
from custom_components.sf_symbols.const import (
    CACHE_IMMUTABLE,
    CACHE_IMMUTABLE_PRIVATE,
    CONF_SHOW_PANEL,
    DATA_DIR,
    DOMAIN,
    ISSUE_CUPERTINO,
    PANEL_ELEMENT,
    PANEL_URL_PATH,
)
from custom_components.sf_symbols.diagnostics import async_get_config_entry_diagnostics
from custom_components.sf_symbols.symbols import (
    MODULE_FILE,
    PANEL_FILE,
    SymbolDataError,
    build_variants,
    load_symbol_data,
)

META = json.loads((DATA_DIR / "meta.json").read_text(encoding="utf-8"))


async def test_setup_registers_module(hass: HomeAssistant, frontend: UrlManager, setup: MockConfigEntry) -> None:
    url = module_url(setup.runtime_data)
    assert url in frontend.urls
    manifest = Path(__file__).parents[1] / "custom_components/sf_symbols/manifest.json"
    version = json.loads(manifest.read_text())["version"]
    assert url.startswith(f"/sf_symbols/{version}-") and url.endswith("/sf-symbols.js")
    assert setup.runtime_data.symbol_count == META["symbols"] > 9000
    assert setup.runtime_data.set_version == META["set_version"]


async def test_module_served_with_config(
    hass: HomeAssistant, setup: MockConfigEntry, hass_client_no_auth: ClientSessionGenerator
) -> None:
    client = await hass_client_no_auth()
    resp = await client.get(module_url(setup.runtime_data))
    assert resp.status == 200
    assert resp.headers["Cache-Control"] == CACHE_IMMUTABLE
    assert resp.content_type == "text/javascript"
    body = await resp.text()
    assert "__SF_CONFIG__" not in body
    assert f'"version": "{setup.runtime_data.version}"' in body
    assert '"chunks": 256' in body


async def test_data_served_gzip(
    hass: HomeAssistant, setup: MockConfigEntry, hass_client: ClientSessionGenerator
) -> None:
    client = await hass_client()
    base = f"/sf_symbols/{setup.runtime_data.version}"
    resp = await client.get(f"{base}/m/00.json")
    assert resp.status == 200
    assert resp.headers["Content-Encoding"] == "gzip"
    assert resp.headers["Cache-Control"] == CACHE_IMMUTABLE_PRIVATE
    assert isinstance(await resp.json(), dict)  # aiohttp decompresses by itself
    resp = await client.get(f"{base}/index.json")
    index = await resp.json()
    assert len(index) == META["listed"]
    assert (await client.get(module_url(setup.runtime_data))).status == 200
    assert (await client.get(panel_url(setup.runtime_data))).status == 200
    # second request comes from the memory cache, without file access and without the executor
    with (
        patch.object(Path, "read_bytes", side_effect=AssertionError("not cached")),
        patch.object(hass, "async_add_executor_job", side_effect=AssertionError("executor used")),
    ):
        assert (await client.get(f"{base}/index.json")).status == 200
        assert (await client.get(module_url(setup.runtime_data))).status == 200
        assert (await client.get(panel_url(setup.runtime_data))).status == 200


async def test_data_needs_login(
    hass: HomeAssistant, setup: MockConfigEntry, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Without login: modules yes (they contain no symbols), data no (401)."""
    client = await hass_client_no_auth()
    v = setup.runtime_data.version
    assert (await client.get(module_url(setup.runtime_data))).status == 200
    for path in ("index.json", "variants.json", "m/00.json", "v/1f.json", "m/zz.json"):
        resp = await client.get(f"/sf_symbols/{v}/{path}")
        assert resp.status == 401, path
    resp = await client.get(f"/sf_symbols/{v}/index.json", headers={"Authorization": "Bearer falsch"})
    assert resp.status == 401


async def test_old_version_not_cached(
    hass: HomeAssistant,
    setup: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    client = await hass_client()
    resp = await client.get("/sf_symbols/0.9.0-alt/v/1f.json")
    assert resp.status == 200
    assert resp.headers["Cache-Control"] == "no-cache"
    resp = await (await hass_client_no_auth()).get("/sf_symbols/0.9.0-alt/sf-symbols.js")
    assert resp.status == 200
    assert resp.headers["Cache-Control"] == "no-cache"


async def test_bad_paths_404(hass: HomeAssistant, setup: MockConfigEntry, hass_client: ClientSessionGenerator) -> None:
    client = await hass_client()
    v = setup.runtime_data.version
    for path in ("meta.json", "m/zz.json", "m/00.json.gz", "../manifest.json", "m/../../__init__.py", "x/00.json"):
        resp = await client.get(f"/sf_symbols/{v}/{path}")
        assert resp.status == 404, path
    # valid name, but the file is missing
    with patch.object(setup.runtime_data, "load", return_value=None):
        assert (await client.get(f"/sf_symbols/{v}/m/ff.json")).status == 404
    # the modules are only served through the public route, never as "data"
    view = SFSymbolsDataView(hass)
    for file in (MODULE_FILE, PANEL_FILE):
        resp = await view.get(make_mocked_request("GET", "/"), v, file)
        assert resp.status == 404, file


async def test_unload_removes_everything(
    hass: HomeAssistant,
    frontend: UrlManager,
    setup: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    url = module_url(setup.runtime_data)
    assert await hass.config_entries.async_unload(setup.entry_id)
    assert setup.state is ConfigEntryState.NOT_LOADED
    assert url not in frontend.urls
    client = await hass_client_no_auth()
    assert (await client.get(url)).status == 404
    data_url = url.replace(MODULE_FILE, "index.json")
    assert (await (await hass_client()).get(data_url)).status == 404
    assert await hass.config_entries.async_remove(setup.entry_id)


async def test_missing_data_is_translated_error(hass: HomeAssistant, frontend: UrlManager, tmp_path: Path) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="SF Symbols", data={})
    entry.add_to_hass(hass)
    with patch("custom_components.sf_symbols.DATA_DIR", tmp_path):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason and "symbol data" in entry.reason
    assert not frontend.urls


def test_load_symbol_data_checks(tmp_path: Path) -> None:
    js = tmp_path / "a.js"
    js.write_text("x", encoding="utf-8")
    (tmp_path / "meta.json").write_text('{"symbols": 3}', encoding="utf-8")
    (tmp_path / "m").mkdir()
    try:
        load_symbol_data(tmp_path, js, "1")  # panel module missing: incomplete install
    except SymbolDataError:
        pass
    else:  # pragma: no cover
        raise AssertionError("missing panel module accepted")
    (tmp_path / PANEL_FILE).write_text("p", encoding="utf-8")
    (tmp_path / "m").rmdir()
    (tmp_path / "meta.json").write_text("{nope", encoding="utf-8")
    try:
        load_symbol_data(tmp_path, js, "1")
    except SymbolDataError:
        pass
    else:  # pragma: no cover
        raise AssertionError("broken meta accepted")
    (tmp_path / "meta.json").write_text('{"symbols": 3}', encoding="utf-8")
    try:
        load_symbol_data(tmp_path, js, "1")  # m/ missing
    except SymbolDataError:
        pass
    else:  # pragma: no cover
        raise AssertionError("missing chunks accepted")
    (tmp_path / "m").mkdir()
    data = load_symbol_data(tmp_path, js, "1")
    assert data.version.startswith("1-x-")
    assert data.data_file("m/00.json") is None  # file missing
    assert data.data_file("meta.json") is None  # not a data path
    assert data.set_version == "?"


async def test_cupertino_conflict_issue(hass: HomeAssistant, frontend: UrlManager) -> None:
    hass.config.components.add("cupertino")
    entry = MockConfigEntry(domain=DOMAIN, title="SF Symbols", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_CUPERTINO)
    assert issue is not None and issue.severity is ir.IssueSeverity.WARNING
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["cupertino_installed"] is True
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_CUPERTINO) is None


async def test_conflict_rechecked_after_start(hass: HomeAssistant, frontend: UrlManager) -> None:
    hass.set_state(CoreState.not_running)
    entry = MockConfigEntry(domain=DOMAIN, title="SF Symbols", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_CUPERTINO) is None
    hass.config.components.add("cupertino")  # loads after us
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_CUPERTINO) is not None
    # gone again → the notice disappears on the next load
    hass.config.components.remove("cupertino")
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_CUPERTINO) is None


async def test_diagnostics(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    diag = await async_get_config_entry_diagnostics(hass, setup)
    assert diag["symbols"] == META["symbols"]
    assert diag["set_version"] == META["set_version"]
    assert diag["hierarchical"] > 5000 and diag["multicolor"] > 2000
    assert diag["cupertino_installed"] is False
    assert diag["module_url"].endswith("/sf-symbols.js")


def test_chunks_match_meta() -> None:
    """Every chunk is valid gzip JSON, the sum matches meta.json."""
    total = 0
    for file in sorted((DATA_DIR / "m").glob("*.json.gz")):
        chunk = json.loads(gzip.decompress(file.read_bytes()))
        total += sum(1 for v in chunk.values() if isinstance(v, list))
    assert total == META["symbols"]
    assert len(list((DATA_DIR / "v").glob("*.json.gz"))) == META["chunks"]


def test_module_matches_hashed_source_and_unreadable_chunk(tmp_path: Path) -> None:
    """The module comes from the content hashed at load time (file changed later → URL still matches);
    an unreadable data file gives None (404) with a warning instead of a server error."""
    js = tmp_path / "a.js"
    js.write_text("const CONFIG = /*__SF_CONFIG__*/{};", encoding="utf-8")
    (tmp_path / PANEL_FILE).write_text("panel", encoding="utf-8")
    (tmp_path / "meta.json").write_text('{"symbols": 3}', encoding="utf-8")
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "00.json.gz").mkdir()  # directory instead of a file: read_bytes fails
    data = load_symbol_data(tmp_path, js, "1")
    js.write_text("changed", encoding="utf-8")
    (tmp_path / PANEL_FILE).write_text("changed", encoding="utf-8")
    assert data.load(MODULE_FILE).startswith(b'const CONFIG = {"frame": 24')
    assert data.load(PANEL_FILE) == b"panel"
    with patch("custom_components.sf_symbols.symbols._LOGGER") as logger:
        assert data.data_file("m/00.json") is None
    assert logger.warning.call_args.args[1] == "00.json.gz"


async def test_panel_registered_for_admins(
    hass: HomeAssistant, setup: MockConfigEntry, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Symbol browser in the sidebar: admins only, panel module public and versioned like the loader."""
    panel = hass.data[DATA_PANELS][PANEL_URL_PATH]
    assert panel.component_name == "custom"
    assert panel.require_admin is True
    assert panel.sidebar_title == "SF Symbols"
    custom = panel.config["_panel_custom"]
    assert custom["name"] == PANEL_ELEMENT
    assert custom["module_url"] == panel_url(setup.runtime_data)
    assert custom["embed_iframe"] is False
    # same version directory as the loader: its relative import "./sf-symbols.js" hits the same URL
    assert panel_url(setup.runtime_data).rsplit("/", 1)[0] == module_url(setup.runtime_data).rsplit("/", 1)[0]
    url = panel_url(setup.runtime_data)
    client = await hass_client_no_auth()
    resp = await client.get(url)
    assert resp.status == 200
    assert resp.content_type == "text/javascript"
    assert resp.headers["Cache-Control"] == CACHE_IMMUTABLE
    body = await resp.text()
    assert 'customElements.define("sf-symbols-panel"' in body
    assert 'import "./sf-symbols.js"' in body
    # unload removes the sidebar entry
    assert await hass.config_entries.async_unload(setup.entry_id)
    assert PANEL_URL_PATH not in hass.data[DATA_PANELS]
    assert (await client.get(url)).status == 404


async def test_panel_can_be_turned_off(hass: HomeAssistant, frontend: UrlManager) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="SF Symbols", data={}, options={CONF_SHOW_PANEL: False})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert PANEL_URL_PATH not in hass.data.get(DATA_PANELS, {})
    # icons keep working without the panel
    assert module_url(entry.runtime_data) in frontend.urls
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["show_panel"] is False
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_variants_served(
    hass: HomeAssistant, setup: MockConfigEntry, hass_client: ClientSessionGenerator
) -> None:
    """variants.json: names with a hierarchical/multicolor variant, built from v/ once, then from memory."""
    client = await hass_client()
    resp = await client.get(f"/sf_symbols/{setup.runtime_data.version}/variants.json")
    assert resp.status == 200
    assert resp.headers["Content-Encoding"] == "gzip"
    assert resp.headers["Cache-Control"] == CACHE_IMMUTABLE_PRIVATE
    variants = await resp.json()
    assert set(variants) == {"h", "m"}
    assert "cloud.sun.fill" in variants["h"] and "cloud.sun.fill" in variants["m"]
    assert "lamp.floor" not in variants["m"]
    assert len(variants["h"]) >= META["hierarchical"] and len(variants["m"]) >= META["multicolor"]
    assert variants["m"] == sorted(variants["m"])
    with patch.object(Path, "read_bytes", side_effect=AssertionError("not cached")):
        assert (await client.get(f"/sf_symbols/{setup.runtime_data.version}/variants.json")).status == 200


def test_variants_from_chunks(tmp_path: Path) -> None:
    (tmp_path / "v").mkdir()
    chunk = {"b.fill": {"h": [], "m": []}, "a": {"h": []}}
    (tmp_path / "v" / "00.json.gz").write_bytes(gzip.compress(json.dumps(chunk).encode()))
    assert build_variants(tmp_path) == {"h": ["a", "b.fill"], "m": ["b.fill"]}
    # damaged chunk: 404 with a warning, no server error
    js = tmp_path / "a.js"
    js.write_text("x", encoding="utf-8")
    (tmp_path / PANEL_FILE).write_text("p", encoding="utf-8")
    (tmp_path / "meta.json").write_text('{"symbols": 1}', encoding="utf-8")
    (tmp_path / "m").mkdir()
    (tmp_path / "v" / "01.json.gz").write_bytes(b"not gzip")
    data = load_symbol_data(tmp_path, js, "1")
    with patch("custom_components.sf_symbols.symbols._LOGGER") as logger:
        assert data.data_file("variants.json") is None
    assert logger.warning.called


async def test_panel_path_taken_keeps_icons(hass: HomeAssistant, frontend: UrlManager) -> None:
    """A dashboard already uses /sf-symbols: icons still load, the browser is skipped, the dashboard stays."""
    async_register_built_in_panel(hass, "lovelace", frontend_url_path=PANEL_URL_PATH)
    entry = MockConfigEntry(domain=DOMAIN, title="SF Symbols", data={})
    entry.add_to_hass(hass)
    with patch("custom_components.sf_symbols._LOGGER") as logger:
        assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert module_url(entry.runtime_data) in frontend.urls
    assert hass.data[DATA_PANELS][PANEL_URL_PATH].component_name == "lovelace"
    assert "already in use" in logger.warning.call_args.args[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.data[DATA_PANELS][PANEL_URL_PATH].component_name == "lovelace"
