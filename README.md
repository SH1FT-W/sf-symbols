# SF Symbols for Home Assistant

> **Private repository.** SF Symbols are the property of Apple Inc. and are licensed only for use in apps on
> Apple platforms; they must not be redistributed. The icon data in this repository is generated locally from the
> installed SF Symbols app (`tools/build_icons.py`) and must never be published. Keep this repository private.

A Home Assistant integration that makes Apple's SF Symbols available as icons everywhere in the UI:

- `sf:` with Apple's names, e.g. `sf:lamp.floor`, `sf:cloud.sun.fill`
- `ios:` compatible with [Cupertino Icons](https://github.com/menahishayan/HomeAssistant-Cupertino-Icons), e.g.
  `ios:lamp-floor` — it replaces Cupertino Icons without changing any dashboard, entity or Casora setting.

## Features

- **9,524 symbols** of SF Symbols 27.0 (Cupertino Icons 5.0.1: 6,945). Every Cupertino name resolves; renamed
  Apple symbols resolve through Apple's alias tables.
- **Variants**: append `#hierarchical` (`#h`) or `#multicolor` (`#m`), e.g. `sf:cloud.sun.fill#multicolor`.
  6,440 symbols have hierarchical layers, 2,749 have multicolor. Symbols without that variant stay monochrome.
  Cupertino's suffixes (`#color`, `#invert`, `#fullcolor`) draw monochrome, as before.
- **Icon picker** with search: Apple's keywords and categories plus German terms (e.g. "Stehlampe", "Glühbirne").
- **Two sizes of frame**: `ios:` uses a tight box like Cupertino (same look as before). `sf:` uses a shared square
  frame, so all symbols have the same stroke weight and line up with MDI icons.
- **Fast**: outlines are bundled in 256 gzip chunks (≈20 KB each), loaded on demand and cached for a year;
  the URLs carry a version, so an update reaches every browser at once.

## Installation

1. Copy `custom_components/sf_symbols` into your `config/custom_components` (Daniel: via Privat-Updates).
2. Restart Home Assistant.
3. **Settings → Devices & services → Add integration → SF Symbols**, confirm.
4. Reload the browser tab.

If Cupertino Icons is still installed, a repair notice asks you to remove it. Until then SF Symbols keeps the
`ios:` prefix (it knows every Cupertino name), so nothing breaks.

## Use cases and examples

```yaml
# Entity icon (UI: entity settings → icon)
icon: sf:lightbulb.max
# Tile card with a coloured weather symbol
type: tile
entity: weather.home
icon: sf:cloud.sun.fill#multicolor
# Existing Cupertino icons keep working
icon: ios:lamp-floor
```

White parts of multicolor symbols can be adapted with the CSS variable `--sf-symbols-white`.

## How the data is made

`uv run tools/build_icons.py` (macOS, SF Symbols app, Xcode command line tools):
macOS draws every symbol in monochrome, hierarchical and multicolor into vector PDFs (`tools/render_symbols.swift`);
the script resolves Apple's masks with path booleans and writes plain SVG paths, plus names, aliases and keywords
from the app's metadata. Takes about 25 seconds. `uv run tools/preview.py out.png lamp.floor house` renders a
contact sheet for a visual check. Data update = run the script after a new SF Symbols app, bump the version.

## Known limitations

- Symbol data must be generated on a Mac with the SF Symbols app; it is not downloaded.
- Hierarchical/multicolor colours are drawn by a small hook into Home Assistant's `ha-svg-icon`. Should that
  break after a frontend update, the icons fall back to Home Assistant's own two-tone rendering.
- Variable values (e.g. `wifi` at 50 %), animations and gradients of SF Symbols are not supported.
- `apple.writing.tools` contains an image in multicolor; that part is left out.
- The icon picker lists every symbol twice (`ios:` and `sf:`), because Home Assistant shows every icon set.

## Troubleshooting

- *Icons are empty*: reload the browser (the module is loaded at page start); check that the integration is set up.
- Diagnostics (integration page → ⋮ → Download diagnostics) shows the symbol set version, counts and the module URL.

## Removal

Delete the integration under **Settings → Devices & services**, then remove `custom_components/sf_symbols` and
restart. Icons using `sf:`/`ios:` will be empty afterwards.
