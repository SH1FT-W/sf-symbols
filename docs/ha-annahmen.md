# HA-Annahmen

<!-- Vorlage aus repo-vorlagen/vorlagen/ha-annahmen.md. Liegt im Repo als docs/ha-annahmen.md.
     Der HA-Beta-Bericht (repo-vorlagen/ha-beta-bericht.md) gleicht diese Liste jeden Monat mit den
     Neuerungen der HA-Beta ab. Nur festhalten, was bei einer Änderung in HA still kaputtginge. -->

Worauf sich dieses Repo bei Home Assistant verlässt. Bei jeder Änderung am Code mitpflegen.

**Getestet mit:** HA 2026.10 · **Mindestversion:** siehe `hacs.json` / `manifest.json`

## Annahmen

| Annahme | Wo im Code | Abgesichert durch |
|---|---|---|
| `frontend.add_extra_js_url` / `remove_extra_js_url` laden ein Modul in jede Seite (auch vor dem Login) | `__init__.py` `async_setup_entry` / `async_unload_entry` | `tests/test_setup.py::test_setup_registers_module`, `test_unload_removes_everything` |
| `HomeAssistantView` mit `requires_auth = False` wird ohne Token ausgeliefert, mit `True` antwortet HA 401 | `__init__.py` `SFSymbolsModuleView`, `SFSymbolsDataView` | `test_module_served_with_config`, `test_data_needs_login` |
| Frontend löst `prefix:name` über `window.customIcons[prefix].getIcon()` auf (liefert `{path, secondaryPath, viewBox}`) und listet den Picker über `getIconList()` | `frontend/sf-symbols.js` `install()`, `getIconList` | `tests/js/sf-symbols.test.mjs` (Auflösen aller Cupertino-Namen) |
| `ha-svg-icon` ist ein Custom Element mit `updated()`-Hook und rendert `path`/`secondaryPath` als SVG-`<path>` in `shadowRoot` | `frontend/sf-symbols.js` Hook an `ha-svg-icon.prototype.updated` | `tests/js/sf-symbols.test.mjs` (Ebenen-Zeichnung); Fallback = HAs `secondaryPath` |
| Token des angemeldeten Nutzers: `window.hassConnection` (Promise `{auth, conn}`) bzw. `<home-assistant>.hass.auth.accessToken`, `auth.expired`/`refreshAccessToken()` | `frontend/sf-symbols.js` `authSource()`, `createAuthFetch()` | `tests/js/sf-symbols.test.mjs` (Auth-Quellen, 401-Retry) |
| HAs Icon-Picker ersetzt Leerzeichen in der Suche durch `-` (Suchbegriffe sind so gespeichert) | `tools/build_icons.py`, `tools/keywords_de.json` | kein Test |
| Repair-Hinweis: `issue_registry.async_create_issue` / `async_delete_issue`, Cupertino erkennbar an `hass.config.components` oder dessen Config-Entries | `__init__.py` `cupertino_present`, `async_update_conflict_issue` | `test_cupertino_conflict_issue`, `test_conflict_rechecked_after_start` |
| `ConfigEntryError` beim Laden wird mit `translation_key` aus `strings.json` angezeigt | `__init__.py` `async_setup_entry` | `test_missing_data_is_translated_error` |

## Fremde Integrationen

Integrationen, deren Entitäten oder Attribute dieses Repo liest (Domain, was genau, wo):

- `cupertino` (HomeAssistant Cupertino Icons): nur Anwesenheit (`hass.config.components`, Config-Entries) für den
  Repair-Hinweis; keine Entitäten.

## Prüfbefehl

Befehl, der die Annahmen gegen eine bestimmte HA-Version prüft (`HA_VERSION=beta` o. ä.), oder „keiner“:

```sh
uv run --python 3.14 --with-requirements requirements_test.txt --with "homeassistant==${HA_VERSION:-2026.10.0}" python -m pytest -q -p no:logging && node --test tests/js/*.test.mjs
```
