# Changelog

## 26.10.5 – 24.10.2026

- Repo öffentlich: Code unter MIT-Lizenz, Symboldaten bleiben Apples Eigentum (Hinweis in LICENSE und README). README mit HACS-Installation (benutzerdefiniertes Repository) und Lizenzabschnitt, Privat-Hinweise entfernt.
- Intern: `docs/ha-annahmen.md` (worauf das Modul bei Home Assistant baut), Projektregeln angepasst, Testdaten-Kommentar neutral.

## 26.10.4 – 19.10.2026

- Lade-Modul kommt aus dem Inhalt, der beim Start für die Versionsnummer in der URL gehasht wurde (kein zweites Lesen der Datei, URL und Inhalt passen immer zusammen, auch wenn die Datei vor einem Neustart ersetzt wird).
- Unlesbare Symboldatei: 404 mit einer Warnung im Log statt eines Serverfehlers; der nächste Abruf versucht es erneut.
- Browser-Konsole: eine Warnung, wenn die Symboldaten nicht erreichbar sind (offline, Token abgelehnt), statt still leerer Symbole.
- Intern: CI-Prüfung aus der gemeinsamen Vorlage (Node-Tests, Übersetzungsprüfung, Frühwarnung gegen die neueste HA), Prüfabläufe ohne fremdes venv (`uv run`, `pythonpath` in `pytest.ini`), gemeinsame `tools/next-version` (nie Nummern überspringen), README-Installationshinweis neutral formuliert. Tests für die neuen Fehlerpfade.

## 26.10.3 – 16.10.2026

- **Neue Versionsnummer:** Ab jetzt zählt die Version nach **Jahr.Monat.Nummer des Releases im Monat**: `26.10.3` ist das dritte Release im Oktober 2026, im nächsten Monat geht es wieder bei `.1` los (z. B. `26.11.1`). Der Sprung von `1.1.0` auf `26.10.3` ist gewollt – Privat-Updates und Home Assistant erkennen `26.10.3` als neuer, das Update erscheint wie gewohnt.
- Test prüft die Lade-URL gegen die Version aus `manifest.json` statt gegen eine feste Nummer (brach sonst bei jedem Release).

## 1.1.0 – 16.10.2026
- Symboldaten (`index.json`, `m/`, `v/`) nur noch mit Home-Assistant-Anmeldung (sonst 401); öffentlich bleibt nur
  das Lade-Modul. Es holt die Daten mit dem Token des angemeldeten Nutzers (auch Companion-App), wartet auf der
  Login-Seite still und erneuert abgelaufene Token. Browser-Cache bleibt (versionierte URLs, `private`, ein Jahr).
- Suche: deutsche Suchbegriffe von 226 auf 328 Einträge (307 → 702 Begriffe) ausgebaut, u. a. Rollladen, Markise,
  Gewitter, Heizkörper, Steckdose, Saugroboter, Präsenz, Leck. Deutsche Begriffe nur noch aus dem Symbolnamen
  (keine Fehltreffer wie „Fernseher“ → `gear`, „Müll“ → `eject`, „Heizung“ → Autositz/Tasse). Mehrwort-Suche in
  natürlicher Reihenfolge („floor lamp“ → `lamp.floor`). Suchbegriffe hängen nur an `sf:`, damit jeder Treffer
  einmal erscheint; die `ios:`-Liste enthält weiter alle Cupertino-Namen.
- `sf:`: alle Symbole im selben Quadrat; die wenigen größeren (breite Text-, Auto-, Akku-Symbole) werden hineinverkleinert.
- Schneller: Hook an `ha-svg-icon` steigt bei einfarbigen/MDI-Symbolen sofort aus, Zwischenspeicher im Browser
  begrenzt, Server prüft den Speicher-Cache vor dem Executor.
- Unbekannte Namen: eine Warnung je Name in der Browser-Konsole. Hinweis „Browser neu laden (ggf. zweimal)“ beim
  Einrichten; README: Varianten erst nach dem Entfernen von Cupertino; Quality Scale um `docs-conditions`/`docs-triggers`.


## 1.0.0 – 16.10.2026
- Erste Fassung als Ersatz für Cupertino Icons 5.0.1: 9524 Symbole aus SF Symbols 27.0 (statt 6945), Präfixe
  `sf:` (Apple-Namen) und `ios:` (Cupertino-kompatibel, alle 6945 Namen lösen auf), umbenannte Symbole über Apples Aliase.
- Varianten `#hierarchical` und `#multicolor`; weiße Teile mehrfarbiger Symbole bekommen die Textfarbe
  (Apple-Weiß über `--sf-symbols-white: #ffffff`).
- Symbol-Picker mit Apples Suchbegriffen und deutschen Begriffen.
- Daten in 256 gzip-Stücken mit versionierten URLs und Jahres-Cache.
- Hinweis unter Reparaturen, solange Cupertino Icons noch installiert ist; Diagnose; Quality Scale (selbst geprüft) Platin.
