# SF Symbols – Projektregeln

Private HA-Integration (`custom_components/sf_symbols`, Domain `sf_symbols`), ersetzt „HomeAssistant Cupertino Icons“
(`cupertino`, v5.0.1). Symbolsätze `sf:` (Apple-Namen) und `ios:` (Cupertino-Schreibweise `.`→`-`).

## Regeln

- **Repo bleibt privat.** SF Symbols gehören Apple, Lizenz nur für Apps auf Apple-Plattformen, keine Weitergabe.
  Die Daten unter `custom_components/sf_symbols/data/` nie veröffentlichen (kein öffentliches Repo, kein HACS-Default,
  keine Bilder davon in öffentlichen Issues). Logo ohne Apple-Logo/-Symbole (eigene Zeichnung).
- Lokal committen ok. **Push / GitHub-Repo anlegen nur nach Rückfrage.**
- Prod-HA (192.168.10.30) nur auf Daniels ausdrücklichen Wunsch; Updates laufen über Privat-Updates
  (`~/Software/privat-updates`), nie selbst nach Prod kopieren, kein Neustart ohne Rückfrage.
- Versionen = Kalender-Schema `YY.M.N` (Jahr, Monat ohne Null, N = laufendes Release im Monat ab 1; ab 26.10.x,
  kein X.Y.Z mehr): jede Änderung = neue Version in `manifest.json` + CHANGELOG, `tools/next-version` rechnet sie aus
  (zählt nur echte, veröffentlichte GitHub-Releases des Monats, auch alte X.Y.Z, bloße Tags nicht; ohne Release im Monat → .1; jedes Release als GitHub-Release veröffentlichen). Tag/Release-Titel = genau diese Nummer ohne „v“.
- Deutsche Suchbegriffe (`tools/keywords_de.json`) greifen nur über Namensteile/-anfänge, nicht über Apples
  englische Keywords (zu ungenau). HAs Picker macht aus Leerzeichen „-“ → Suchbegriffe mit „-“ speichern.
- Kompatibilität: alle `ios:`-Namen aus `tests/data/` müssen auflösen (Prod-Entitäten, Dashboards
  `mein-zuhause`/`-mobile`, Casora). Casora prüft per `getIconList()` auf `…-fill`/`…-inverse` – die `ios:`-Liste
  muss Cupertino-Schreibweise behalten. `ios:` bleibt im engen Rahmen (Casora skaliert `lamp-floor`/`lamp-table` 0.68).

## Entscheidungen (Daniel, 16.10.2026)

- Logo: Variante A „Kachel“ (Haus + Funkeln) ist endgültig; B/C bleiben nur als Entwürfe in `docs/logo-varianten/`.
- Weiß in mehrfarbigen Symbolen = `var(--sf-symbols-white, var(--primary-text-color))`, nicht Apple-Weiß
  (im hellen Design sonst unsichtbar). Wer Apple-Weiß will, setzt die Variable selbst.
- Doppelte Einträge im Picker (`ios:` + `sf:`) bleiben bewusst: die `ios:`-Liste braucht Casora für die
  `-fill`-Prüfung, HAs Picker zeigt jeden Satz. Seit 1.1.0 tragen nur `sf:`-Einträge Suchbegriffe (Suchwörter
  zeigen jedes Symbol einmal), `ios:` wird nur über den Namen gefunden.
- `sf:`-Rahmen bleibt bewusst MDI-groß (Kreis-Symbol / 0.85), `ios:` eng wie Cupertino. Seit 1.1.0 ist das
  Quadrat für alle `sf:` gleich; größere Symbole (~27 %, meist breite) werden im Frontend hineinverkleinert.

## Aufbau

- `tools/build_icons.py` (uv-Skript) + `tools/render_symbols.swift`: macOS zeichnet jedes Symbol per SwiftUI
  `ImageRenderer` in Vektor-PDFs (mono/hierarchisch/mehrfarbig); das Skript liest die PDF-Operatoren, löst
  SMasks (Luminosity/Alpha = Aussparungen) mit skia-pathops auf → einfache SVG-Pfade (nonzero), 256 gzip-Stücke
  (`m/` Umrisse, `v/` Ebenen) nach FNV-1a-Hash des Namens, `index.json.gz` (Picker-Liste + Suchbegriffe),
  `meta.json` (Satz-Version, Anzahl, Hash). Deutsche Suchbegriffe: `tools/keywords_de.json` (handgeschrieben,
  die App hat keine deutschen Keywords). Neuer Satz: App aktualisieren, Skript laufen lassen, Version erhöhen (nächste per `tools/next-version`).
- `tools/preview.py` = PNG-Kontaktbogen zum Ansehen, `tools/logos.py` = Logo-Varianten/Vergleich/brand.
- Server: `SFSymbolsModuleView` liefert `/sf_symbols/<version>/sf-symbols.js` öffentlich, `SFSymbolsDataView`
  `index.json`, `m/xx.json`, `v/xx.json` nur mit Login (`requires_auth`, sonst 401; gzip, `private … immutable`
  nur bei aktueller Version, sonst `no-cache`; 404 ohne geladenen Eintrag). Speicher-Cache wird im Event-Loop geprüft.
  Version = Integrationsversion + Daten-Hash + JS-Hash → Cache-Busting.
- Frontend `frontend/sf-symbols.js`: `window.customIcons.sf/.ios` (per `defineProperty`, hat Vorrang vor Cupertino),
  Daten per Token aus `window.hassConnection` bzw. `<home-assistant>.hass.auth` (wartet auf der Login-Seite),
  Varianten über Hook in `ha-svg-icon.updated` (Ebenen-Map nach Pfad; Fallback = HAs `secondaryPath`).
- Konflikt: Cupertino geladen/eingerichtet → Repair-Hinweis `cupertino_installed` (nach Start erneut geprüft).

## Prüfen

- `~/Software/evenlight/.venv/bin/python -m pytest -q -p no:logging --cov=custom_components/sf_symbols`
- `node --test tests/js/*.test.mjs` (Frontend gegen die echten Daten, inkl. aller 6945 Cupertino-Namen)
- `uvx ruff check . && uvx ruff format --check .`, `uvx mypy@2.3.1 --python-executable ~/Software/evenlight/.venv/bin/python`
- hassfest: `docker run --rm -v "$PWD/custom_components/sf_symbols:/github/workspace/custom_components/sf_symbols" ghcr.io/home-assistant/hassfest`
- Live: Wegwerf-Container (16.10.: `sf-symbols-test` auf :8150, Onboarding per API, Token in `hassTokens`,
  Playwright aus `~/.npm/_npx`), danach löschen.
