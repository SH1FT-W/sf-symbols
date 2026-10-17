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
- **Icon picker** with search: Apple's keywords and categories plus German smart-home terms (e.g. "Stehlampe",
  "Rollladen", "Heizung", "Steckdose"). Multi-word searches work in natural order ("floor lamp" → `lamp.floor`).
  Search terms are attached to `sf:` only, so a search shows each symbol once; the `ios:` list still contains
  every Cupertino name (found by name).
- **Two sizes of frame**: `ios:` uses a tight box like Cupertino (same look as before). Every `sf:` symbol gets
  the same square frame (circle size / 0.85, like MDI's padding), so symbols share one scale and stroke weight
  and line up with MDI icons. Symbols larger than that square (about a quarter, mostly wide ones such as text
  formats, car or battery-stack symbols; also `lamp.floor` by 2 %) are scaled down into it.
- **Fast**: outlines are bundled in 256 gzip chunks (≈20 KB each), loaded on demand and cached for a year
  in the browser; the URLs carry a version, so an update reaches every browser at once.
- **Only for logged-in users**: the loader module is public (browsers load it before login), the symbol data
  (`index.json`, `m/`, `v/`) is only served with a Home Assistant login (401 otherwise). The module fetches it
  with the logged-in user's token, also in the Companion app.

## Installation

1. Copy `custom_components/sf_symbols` into your `config/custom_components` (or via Privat-Updates).
2. Restart Home Assistant.
3. **Settings → Devices & services → Add integration → SF Symbols**, confirm.
4. Reload the browser tab (if icons stay empty, reload a second time – the browser may still have the old page cached).

If Cupertino Icons is still installed, a repair notice asks you to remove it. Until then SF Symbols keeps the
`ios:` prefix (it knows every Cupertino name), so nothing breaks. **Variants** (`#hierarchical`, `#multicolor`)
only work once Cupertino Icons is removed: Cupertino's own module still hooks into the icon rendering and draws
those suffixes its own way.

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

White parts of multicolor symbols (e.g. the cloud in `cloud.sun.fill`) use the text colour
(`var(--primary-text-color)`), so they stay visible in light themes. For Apple's original white, set the CSS
variable `--sf-symbols-white: #ffffff` (e.g. in your theme or via card-mod/UIX).

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

- *Icons are empty*: reload the browser (the module is loaded at page start), if needed twice because of the
  browser cache; check that the integration is set up. The data needs a login: on the login page or with an
  expired session icons stay empty until you are logged in.
- *Unknown name*: the browser console shows `SF Symbols: unknown icon …` once per name.
- *Variants stay monochrome*: remove Cupertino Icons (see Installation).
- Diagnostics (integration page → ⋮ → Download diagnostics) shows the symbol set version, counts and the module URL.

## Removal

Delete the integration under **Settings → Devices & services**, then remove `custom_components/sf_symbols` and
restart. Icons using `sf:`/`ios:` will be empty afterwards.
