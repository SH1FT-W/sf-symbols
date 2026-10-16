# Changelog

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
