# SF Symbols – Projektregeln

Öffentliche HA-Integration (SH1FT-W/sf-symbols, seit 24.10.2026; vorher privat) (`custom_components/sf_symbols`, Domain `sf_symbols`), ersetzt „HomeAssistant Cupertino Icons“
(`cupertino`, v5.0.1). Symbolsätze `sf:` (Apple-Namen) und `ios:` (Cupertino-Schreibweise `.`→`-`).

## Regeln

- **Lizenz:** Code MIT (SH1FT-W), Symboldaten unter `custom_components/sf_symbols/data/` gehören Apple und stehen
  nicht unter MIT (Hinweis in NOTICE und README, LICENSE bleibt reines MIT, sonst erkennt GitHub/HACS die Lizenz nicht; so wie Cupertino Icons es handhabt). Apples Marken-Symbole
  (Apple-Logo, Produktmarken) nie aufnehmen; Logo ohne Apple-Logo/-Symbole (eigene Zeichnung). Für den Marketplace (hacs/default) eingereicht: Daniels Entscheidung 05.11.2026.
- Lokal committen ok. **Push nur nach Rückfrage.** README englisch.
- Nichts Persönliches ins Repo (keine Heim-IPs, Entitätslisten nur anonymisiert in `tests/data/`).
- Prod-HA nur auf ausdrücklichen Wunsch; Updates laufen über den Marketplace (HACS),
  nie selbst nach Prod kopieren, kein Neustart ohne Rückfrage.
- Versionen über `tools/next-version` (globale Regeln): jede Änderung = neue Version in `manifest.json` + CHANGELOG.
- Deutsche Suchbegriffe (`tools/keywords_de.json`, handgeschrieben, die App hat keine deutschen) greifen nur über
  Namensteile/-anfänge, nicht über Apples englische Keywords (zu ungenau). HAs Picker macht aus Leerzeichen „-“ →
  Suchbegriffe mit „-“ speichern.
- Kompatibilität: alle `ios:`-Namen aus `tests/data/` müssen auflösen (Prod-Entitäten, Dashboards
  Casora). Casora prüft per `getIconList()` auf `…-fill`/`…-inverse` – die `ios:`-Liste
  muss Cupertino-Schreibweise behalten. `ios:` bleibt im engen Rahmen (Casora skaliert `lamp-floor`/`lamp-table` 0.68).

## Entscheidungen (16.10.2026)

- Logo: Variante A „Kachel“ (Haus + Funkeln) ist endgültig; B/C bleiben nur als Entwürfe in `docs/logo-varianten/`.
- Weiß in mehrfarbigen Symbolen = `var(--sf-symbols-white, var(--primary-text-color))`, nicht Apple-Weiß
  (im hellen Design sonst unsichtbar). Wer Apple-Weiß will, setzt die Variable selbst.
- Doppelte Einträge im Picker (`ios:` + `sf:`) bleiben bewusst: die `ios:`-Liste braucht Casora für die
  `-fill`-Prüfung, HAs Picker zeigt jeden Satz. Seit 1.1.0 tragen nur `sf:`-Einträge Suchbegriffe (Suchwörter
  zeigen jedes Symbol einmal), `ios:` wird nur über den Namen gefunden.
- `sf:`-Rahmen bleibt bewusst MDI-groß (Kreis-Symbol / 0.85), `ios:` eng wie Cupertino. Seit 1.1.0 ist das
  Quadrat für alle `sf:` gleich; größere Symbole (~27 %, meist breite) werden im Frontend hineinverkleinert.

## Aufbau

- `tools/build_icons.py` (uv-Skript) + `tools/render_symbols.swift`: macOS zeichnet jedes Symbol per SwiftUI in
  Vektor-PDFs, das Skript macht daraus einfache SVG-Pfade in gzip-Stücken unter `data/`. Neuer Satz: App
  aktualisieren, Skript laufen lassen, Version erhöhen.
- `tools/preview.py` = PNG-Kontaktbogen zum Ansehen, `tools/logos.py` = Logo-Varianten/Vergleich/brand.
- `__init__.py` Server: Lade-Modul und Panel öffentlich, Symboldaten nur mit Login; Version (Integration + Daten-
  + JS-Hash) im Pfad → Cache-Busting. Repair-Hinweis `cupertino_installed`, solange Cupertino da ist.
- `custom_components/sf_symbols/frontend/`: `sf-symbols.js` Lade-Modul (`window.customIcons.sf/.ios`), `sf-symbols-panel.js` Symbol-Browser
  (Seitenleisten-Panel seit 26.11.1, nur Admins, Option `show_panel`).

## Warum es so ist (steht nicht im Code)

- `customIcons` per `defineProperty`, damit SF Symbols Vorrang vor Cupertino hat.
- Panel-Höhe `100dvh` minus Safe-Area-Insets: HAs Container hat keine feste Höhe, polstert aber die Insets; ohne
  feste Höhe 8000 Zellen + Abrufsturm.
- Das Panel importiert `./sf-symbols.js` aus demselben Versionsverzeichnis → dieselbe Instanz wie das Lade-Modul.

## Prüfen

- Tests: `uv run --python 3.14 --with-requirements requirements_test.txt python -m pytest -q -p no:logging`
  (`pytest.ini` setzt `pythonpath = .`, `pytest` direkt geht ebenso; Coverage mit `--with pytest-cov
  … --cov=custom_components/sf_symbols`).
- `node --test tests/js/*.test.mjs` (Frontend gegen die echten Daten, inkl. aller 6945 Cupertino-Namen)
- `uvx ruff@0.16.9 check . && uvx ruff@0.16.9 format --check .` (Version wie in pruefung.yml)
- Typen: einmal `uv venv --python 3.14 /tmp/venv-sf-symbols && uv pip install --python /tmp/venv-sf-symbols/bin/python
  -r requirements_test.txt`, dann `uvx mypy@2.3.1 --python-executable /tmp/venv-sf-symbols/bin/python`.
- Übersetzungen: `python3 tools/pruefe-uebersetzungen.py` (Vorlage aus repo-vorlagen, byteidentisch, von ruff
  ausgenommen).
- CI: `.github/workflows/pruefung.yml` (Vorlage repo-vorlagen/vorlagen/ci-ha-integration.yml, COV_MIN 98, gemessen
  100) macht dasselbe plus Node-Tests und hassfest; montags zusätzlich gegen die neueste HA (darf rot sein).
- `tools/next-version` ist die gemeinsame Fassung aus repo-vorlagen/vorlagen (byteidentisch, Abgleich dort).
- HA-Annahmen: `docs/ha-annahmen.md` (Frontend-Interna, auf die das Modul baut).
- hassfest: `docker run --rm -v "$PWD/custom_components/sf_symbols:/github/workspace/custom_components/sf_symbols" ghcr.io/home-assistant/hassfest`
- Live: Wegwerf-Container (16.10.: `sf-symbols-test` auf :8150, Onboarding per API, Token in `hassTokens`,
  Playwright aus `~/.npm/_npx`), danach löschen.
