# /// script
# requires-python = ">=3.12"
# dependencies = ["pymupdf>=1.26"]
# ///
"""Render a PNG contact sheet of symbols from the built data (monochrome, hierarchical, multicolor).

Usage: uv run tools/preview.py <out.png> name [name ...] [--data DIR] [--dark]
"""

import argparse
import gzip
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent


def fnv1a(text: str) -> int:
    h = 0x811C9DC5
    for ch in text:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def load(data: Path, sub: str, name: str) -> object:
    chunk = json.loads(gzip.decompress((data / sub / f"{fnv1a(name) % 256:02x}.json.gz").read_bytes()))
    value = chunk.get(name)
    if isinstance(value, str) and sub == "m":
        return load(data, sub, value)
    return value


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("names", nargs="+")
    ap.add_argument("--data", type=Path, default=ROOT / "custom_components" / "sf_symbols" / "data")
    ap.add_argument("--dark", action="store_true")
    a = ap.parse_args()
    fg, bg = ("#ffffff", "#1c1c1e") if a.dark else ("#000000", "#ffffff")
    cell, pad = 120, 10
    rows = []
    for r, name in enumerate(a.names):
        mono = load(a.data, "m", name)
        var = load(a.data, "v", name) or {}
        if not isinstance(mono, list):
            continue
        x, y, w, h, d = mono
        s = (cell - 2 * pad) / max(w, h)

        def g(col: int, inner: str) -> str:
            tx = col * cell + pad + ((cell - 2 * pad) - w * s) / 2 - x * s
            ty = r * (cell + 20) + pad + ((cell - 2 * pad) - h * s) / 2 - y * s
            return f'<g transform="translate({tx:.2f} {ty:.2f}) scale({s:.4f})">{inner}</g>'

        rows.append(g(0, f'<path fill="{fg}" d="{d}"/>'))
        if "h" in var:
            rows.append(g(1, "".join(f'<path fill="{fg}" fill-opacity="{o}" d="{p}"/>' for o, p in var["h"])))
        if "m" in var:
            rows.append(g(2, "".join(f'<path fill="{c or fg}" fill-opacity="{o}" d="{p}"/>' for c, o, p in var["m"])))
        rows.append(
            f'<text x="{3 * cell + 10}" y="{r * (cell + 20) + cell / 2}" font-size="16" fill="{fg}">{name}</text>'
        )
    W, H = 3 * cell + 330, len(a.names) * (cell + 20)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="{bg}"/>{"".join(rows)}</svg>'
    doc = pymupdf.open(stream=svg.encode(), filetype="svg")
    doc[0].get_pixmap(dpi=96).save(a.out)


if __name__ == "__main__":
    main()
