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
- Kompatibilität: alle `ios:`-Namen aus `tests/data/` müssen auflösen (Prod-Entitäten, Dashboards
  `mein-zuhause`/`-mobile`, Casora). Casora prüft per `getIconList()` auf `…-fill`/`…-inverse` – die `ios:`-Liste
  muss Cupertino-Schreibweise behalten. `ios:` bleibt im engen Rahmen (Casora skaliert `lamp-floor`/`lamp-table` 0.68).

## Aufbau

- `tools/build_icons.py` (uv-Skript) + `tools/render_symbols.swift`: macOS zeichnet jedes Symbol per SwiftUI
  `ImageRenderer` in Vektor-PDFs (mono/hierarchisch/mehrfarbig); das Skript liest die PDF-Operatoren, löst
  SMasks (Luminosity/Alpha = Aussparungen) mit skia-pathops auf → einfache SVG-Pfade (nonzero), 256 gzip-Stücke
  (`m/` Umrisse, `v/` Ebenen) nach FNV-1a-Hash des Namens, `index.json.gz` (Picker-Liste + Suchbegriffe),
  `meta.json` (Satz-Version, Anzahl, Hash). Deutsche Suchbegriffe: `tools/keywords_de.json` (handgeschrieben,
  die App hat keine deutschen Keywords). Neuer Satz: App aktualisieren, Skript laufen lassen, Version erhöhen.
- `tools/preview.py` = PNG-Kontaktbogen zum Ansehen, `tools/logos.py` = Logo-Varianten/Vergleich/brand.
- Server: `SFSymbolsView` liefert `/sf_symbols/<version>/{sf-symbols.js,index.json,m/xx.json,v/xx.json}`
  (gzip, `immutable` nur bei aktueller Version, sonst `no-cache`; 404 ohne geladenen Eintrag).
  Version = Integrationsversion + Daten-Hash + JS-Hash → Cache-Busting.
- Frontend `frontend/sf-symbols.js`: `window.customIcons.sf/.ios` (per `defineProperty`, hat Vorrang vor Cupertino),
  Varianten über Hook in `ha-svg-icon.updated` (Ebenen-Map nach Pfad; Fallback = HAs `secondaryPath`).
- Konflikt: Cupertino geladen/eingerichtet → Repair-Hinweis `cupertino_installed` (nach Start erneut geprüft).

## Prüfen

- `~/Software/evenlight/.venv/bin/python -m pytest -q -p no:logging --cov=custom_components/sf_symbols`
- `node --test tests/js/*.test.mjs` (Frontend gegen die echten Daten, inkl. aller 6945 Cupertino-Namen)
- `uvx ruff check . && uvx ruff format --check .`, `uvx mypy@2.3.1 --python-executable ~/Software/evenlight/.venv/bin/python`
- hassfest: `docker run --rm -v "$PWD/custom_components/sf_symbols:/github/workspace/custom_components/sf_symbols" ghcr.io/home-assistant/hassfest`
- Live: Wegwerf-Container (16.10.: `sf-symbols-test` auf :8150, Onboarding per API, Token in `hassTokens`,
  Playwright aus `~/.npm/_npx`), danach löschen.
