# /// script
# requires-python = ">=3.12"
# dependencies = ["resvg-py>=0.2", "pillow>=11"]
# ///
"""Logo-Varianten (docs/logo-varianten/*.svg) als PNG, Vergleichsbild und brand-Dateien erzeugen.

Usage: uv run tools/logos.py [gewählte-variante]   (Standard: a-kachel)
"""

from io import BytesIO
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont
import resvg_py

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "docs" / "logo-varianten"
BRAND = ROOT / "custom_components" / "sf_symbols" / "brand"
NAMES = {
    "a-kachel": "A  Kachel (Haus + Funkeln)",
    "b-raster": "B  Raster (Formen)",
    "c-ebenen": "C  Ebenen (hierarchisch)",
}


def render(name: str, size: int) -> Image.Image:
    data = resvg_py.svg_to_bytes(svg_path=str(DIR / f"{name}.svg"), width=size, height=size)
    return Image.open(BytesIO(bytes(data))).convert("RGBA")


def main() -> None:
    chosen = sys.argv[1] if len(sys.argv) > 1 else "a-kachel"
    for name in NAMES:
        render(name, 512).save(DIR / f"{name}.png")
    width, height = 1260, 760
    img = Image.new("RGB", (width, height), "#f2f2f7")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 380, width, height], fill="#111114")
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    for row, fg in enumerate(("#111111", "#eeeeee")):
        for i, (name, label) in enumerate(NAMES.items()):
            x, y = 40 + i * 410, 30 + row * 380
            for size, (dx, dy) in ((260, (0, 0)), (64, (280, 150)), (32, (280, 226))):
                tile = render(name, size)
                img.paste(tile, (x + dx, y + dy), tile)
            draw.text((x, y + 290), label + ("  (eingebaut)" if name == chosen else ""), fill=fg, font=font)
    img.save(DIR / "vergleich.png")
    BRAND.mkdir(parents=True, exist_ok=True)
    for prefix in ("", "dark_"):
        render(chosen, 256).save(BRAND / f"{prefix}icon.png")
        render(chosen, 512).save(BRAND / f"{prefix}icon@2x.png")


if __name__ == "__main__":
    main()
