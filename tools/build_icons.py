# /// script
# requires-python = ">=3.12"
# dependencies = ["pymupdf>=1.26", "skia-pathops>=0.8"]
# ///
"""Build the SF Symbols icon data from the locally installed SF Symbols app.

SF Symbols are Apple's property and subject to Apple's license terms (see LICENSE). This
script reads the app and macOS on *this* Mac and writes the data into the integration.

How it works:
1. Names, aliases, search terms and categories come from the app's metadata plists
   (``/Applications/SF Symbols.app/Contents/Resources/Metadata``).
2. ``tools/render_symbols.swift`` lets macOS draw every symbol three times (monochrome,
   hierarchical, multicolor) into vector PDFs via SwiftUI's ``ImageRenderer``.
3. This script reads the PDF drawing operators, resolves Apple's soft masks (knockouts such as
   the gap around a badge or a slash) with skia path booleans and writes plain, nonzero-filled
   SVG path data, grouped into 256 gzip-compressed chunks.

Run: ``uv run tools/build_icons.py`` (macOS only, needs Xcode command line tools for swiftc).
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
import gzip
import hashlib
import json
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tempfile
import time
from typing import Any

import pathops
import pymupdf

APP = Path("/Applications/SF Symbols.app")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "custom_components" / "sf_symbols" / "data"
RENDER_PT = 100.0  # render size; output is scaled to SCALE units per point
SCALE = 0.2  # 100 pt -> 20 units, the size of Cupertino's SVGs
CHUNKS = 256
# Name suffixes for localized script variants (Arabic digits, Hindi, Hebrew, ...): they stay
# resolvable, but are left out of the icon picker list.
LOCALE_SUFFIXES = {
    "ar", "he", "hi", "ja", "ko", "th", "zh", "rtl", "bn", "gu", "kn", "km", "ml", "mni", "mr",
    "my", "or", "pa", "sat", "si", "ta", "te", "ur", "el", "ru", "sr", "uk", "vi", "tr", "nl",
    "pl", "cs", "sk", "sv", "da", "fi", "nb", "is", "lt", "lv", "et", "hu", "ro", "hr", "sl",
    "bg", "mk", "ca", "es", "pt", "it", "fr", "de", "id", "ms", "trad", "traditional", "kk",
}  # fmt: skip

TOKEN = re.compile(rb"/[^\s/\[\]()<>]+|[-+]?(?:\d+\.?\d*|\.\d+)|[A-Za-z*'\"]+|\[|\]|<<|>>")


def fnv1a(text: str) -> int:
    """32-bit FNV-1a over the UTF-16 code units (same as the frontend for ASCII names)."""
    h = 0x811C9DC5
    for ch in text:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def chunk_of(name: str) -> int:
    return fnv1a(name) % CHUNKS


# ---------------------------------------------------------------- PDF interpretation


Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mul(m: Matrix, n: Matrix) -> Matrix:
    """m then n (PDF row-vector convention)."""
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F)


def apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


@dataclass
class GState:
    ctm: Matrix = IDENTITY
    rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)
    alpha: float = 1.0
    mask: pathops.Path | None = None  # hidden region (device space) from a soft mask
    clip: pathops.Path | None = None


@dataclass
class Fill:
    rgb: tuple[float, float, float]
    alpha: float
    path: pathops.Path


@dataclass
class Interpreter:
    doc: pymupdf.Document
    unsupported: set[str] = field(default_factory=set)

    def page_fills(self, page: pymupdf.Page) -> list[Fill]:
        data = b"".join(self.doc.xref_stream(x) for x in page.get_contents())
        out: list[Fill] = []
        self.run(data, page.xref, GState(), out)
        return out

    # -- resources
    def _dict_ref(self, xref: int, key: str) -> int | None:
        kind, val = self.doc.xref_get_key(xref, key)
        if kind == "xref":
            return int(val.split()[0])
        return None

    def _resource(self, owner: int, category: str, name: str) -> int | None:
        res = self._dict_ref(owner, "Resources")
        if res is not None:
            kind, val = self.doc.xref_get_key(res, f"{category}/{name}")
        else:
            kind, val = self.doc.xref_get_key(owner, f"Resources/{category}/{name}")
        return int(val.split()[0]) if kind == "xref" else None

    def _matrix(self, xref: int, key: str) -> Matrix:
        kind, val = self.doc.xref_get_key(xref, key)
        if kind != "array":
            return IDENTITY
        nums = [float(v) for v in val.strip("[]").split()]
        return (nums[0], nums[1], nums[2], nums[3], nums[4], nums[5])

    # -- soft mask: hidden region = what the luminosity group paints dark
    def soft_mask(self, gs_xref: int, gs: GState) -> pathops.Path | None:
        kind, val = self.doc.xref_get_key(gs_xref, "SMask")
        if kind == "name" and val == "/None":
            return None
        group = None
        kind, val = self.doc.xref_get_key(gs_xref, "SMask/G")
        if kind == "xref":
            group = int(val.split()[0])
        _kind_s, sub = self.doc.xref_get_key(gs_xref, "SMask/S")
        if group is None or sub not in ("/Luminosity", "/Alpha"):
            self.unsupported.add(f"smask {sub}")
            return None
        if sub == "/Alpha":
            # visible only where the group paints; everything else is hidden
            fills_a: list[Fill] = []
            ctm_a = mul(self._matrix(group, "Matrix"), gs.ctm)
            self.run(self.doc.xref_stream(group), group, GState(ctm=ctm_a), fills_a)
            hidden_a = pathops.Path()
            hidden_a.moveTo(-1e4, -1e4)
            for x, y in ((1e4, -1e4), (1e4, 1e4), (-1e4, 1e4)):
                hidden_a.lineTo(x, y)
            hidden_a.close()
            for f in fills_a:
                if f.alpha >= 0.5:
                    hidden_a = pathops.op(hidden_a, f.path, pathops.PathOp.DIFFERENCE, fix_winding=True)
            return hidden_a
        kind_bc, bc = self.doc.xref_get_key(gs_xref, "SMask/BC")
        if kind_bc == "array" and bc.strip("[] ") not in ("1", "1 1 1"):
            self.unsupported.add(f"smask backdrop {bc}")
        fills: list[Fill] = []
        ctm = mul(self._matrix(group, "Matrix"), gs.ctm)
        self.run(self.doc.xref_stream(group), group, GState(ctm=ctm), fills)
        hidden = pathops.Path()
        for f in fills:
            lum = 0.3 * f.rgb[0] + 0.59 * f.rgb[1] + 0.11 * f.rgb[2]
            if lum * f.alpha + (1 - f.alpha) < 0.5:  # dark -> hides the masked paint
                hidden = pathops.op(hidden, f.path, pathops.PathOp.UNION, fix_winding=True)
            else:
                hidden = pathops.op(hidden, f.path, pathops.PathOp.DIFFERENCE, fix_winding=True)
        return hidden

    # -- content stream
    def run(self, data: bytes, owner: int, gs: GState, out: list[Fill]) -> None:
        stack: list[GState] = []
        operands: list[Any] = []
        path = pathops.Path()
        fill_type = pathops.FillType.WINDING
        cur = (0.0, 0.0)
        pending_clip: pathops.FillType | None = None
        for tok_b in TOKEN.findall(data):
            tok = tok_b.decode("latin1")
            if tok[0] in "-+.0123456789":
                operands.append(float(tok))
                continue
            if tok[0] == "/" or tok in ("[", "]", "<<", ">>"):
                operands.append(tok)
                continue
            op = tok
            if op == "q":
                stack.append(replace(gs))
            elif op == "Q":
                gs = stack.pop() if stack else GState()
            elif op == "cm":
                a, b, c, d, e, f = operands[-6:]
                gs = replace(gs, ctm=mul((a, b, c, d, e, f), gs.ctm))
            elif op == "m":
                cur = apply(gs.ctm, operands[-2], operands[-1])
                path.moveTo(*cur)
            elif op == "l":
                cur = apply(gs.ctm, operands[-2], operands[-1])
                path.lineTo(*cur)
            elif op == "c":
                x1, y1, x2, y2, x3, y3 = operands[-6:]
                p1, p2, cur = apply(gs.ctm, x1, y1), apply(gs.ctm, x2, y2), apply(gs.ctm, x3, y3)
                path.cubicTo(*p1, *p2, *cur)
            elif op == "v":
                x2, y2, x3, y3 = operands[-4:]
                p2, end = apply(gs.ctm, x2, y2), apply(gs.ctm, x3, y3)
                path.cubicTo(*cur, *p2, *end)
                cur = end
            elif op == "y":
                x1, y1, x3, y3 = operands[-4:]
                p1, cur = apply(gs.ctm, x1, y1), apply(gs.ctm, x3, y3)
                path.cubicTo(*p1, *cur, *cur)
            elif op == "h":
                path.close()
            elif op == "re":
                x, y, w, h = operands[-4:]
                pts = [
                    apply(gs.ctm, x, y),
                    apply(gs.ctm, x + w, y),
                    apply(gs.ctm, x + w, y + h),
                    apply(gs.ctm, x, y + h),
                ]
                path.moveTo(*pts[0])
                for p in pts[1:]:
                    path.lineTo(*p)
                path.close()
            elif op in ("W", "W*"):
                pending_clip = pathops.FillType.EVEN_ODD if op == "W*" else pathops.FillType.WINDING
            elif op in ("f", "F", "f*", "B", "B*", "b", "b*", "n", "S", "s"):
                if op in ("f", "F", "f*", "B", "B*", "b", "b*"):
                    path.fillType = pathops.FillType.EVEN_ODD if "*" in op else fill_type
                    shape = pathops.simplify(path, fix_winding=True)
                    if gs.clip is not None:
                        shape = pathops.op(shape, gs.clip, pathops.PathOp.INTERSECTION, fix_winding=True)
                    if gs.mask is not None:
                        shape = pathops.op(shape, gs.mask, pathops.PathOp.DIFFERENCE, fix_winding=True)
                    out.append(Fill(gs.rgb, gs.alpha, shape))
                elif op in ("S", "s"):
                    self.unsupported.add("stroke")
                if pending_clip is not None:
                    path.fillType = pending_clip
                    clip = pathops.simplify(path, fix_winding=True)
                    if gs.clip is not None:
                        clip = pathops.op(clip, gs.clip, pathops.PathOp.INTERSECTION, fix_winding=True)
                    gs = replace(gs, clip=clip)
                    pending_clip = None
                path = pathops.Path()
            elif op in ("sc", "scn", "rg"):
                nums = [o for o in operands if isinstance(o, float)]
                if len(nums) >= 3:
                    gs = replace(gs, rgb=(nums[-3], nums[-2], nums[-1]))
                elif nums:
                    gs = replace(gs, rgb=(nums[-1],) * 3)
            elif op == "g":
                gs = replace(gs, rgb=(operands[-1],) * 3)
            elif op == "gs":
                ref = self._resource(owner, "ExtGState", operands[-1][1:])
                if ref is not None:
                    kind, val = self.doc.xref_get_key(ref, "ca")
                    if kind in ("float", "int"):
                        gs = replace(gs, alpha=float(val))
                    if self.doc.xref_get_key(ref, "SMask")[0] != "null":
                        gs = replace(gs, mask=self.soft_mask(ref, gs))
                    if self.doc.xref_get_key(ref, "BM")[0] != "null":
                        bm = self.doc.xref_get_key(ref, "BM")[1]
                        if bm not in ("/Normal", "/Compatible"):
                            self.unsupported.add(f"blend {bm}")
            elif op == "Do":
                ref = self._resource(owner, "XObject", operands[-1][1:])
                if ref is not None and self.doc.xref_get_key(ref, "Subtype")[1] == "/Form":
                    inner = replace(gs, ctm=mul(self._matrix(ref, "Matrix"), gs.ctm))
                    self.run(self.doc.xref_stream(ref), ref, inner, out)
                else:
                    self.unsupported.add("image")
            elif op in ("cs", "CS", "SC", "SCN", "RG", "G", "w", "J", "j", "M", "d", "ri", "i", "BX", "EX"):
                pass
            else:
                self.unsupported.add(f"op {op}")
            operands = []


# ---------------------------------------------------------------- SVG path output


def fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    return s


def join(nums: list[float]) -> str:
    """Numbers with the fewest separators SVG allows ("1.5.5-2" = 1.5 .5 -2)."""
    out = ""
    last = ""
    for v in nums:
        s = fmt(v)
        if out and not (s.startswith("-") or (s.startswith(".") and "." in last)):
            out += " "
        out += s
        last = s
    return out


class RelPen:
    """Compact relative SVG path data, rounded to 0.01 without drift."""

    def __init__(self, transform: Matrix) -> None:
        self.t = transform
        self.parts: list[str] = []
        self.pos = (0.0, 0.0)
        self.start = (0.0, 0.0)

    def _pt(self, p: tuple[float, float]) -> tuple[float, float]:
        x, y = apply(self.t, *p)
        return (round(x, 2), round(y, 2))

    def _rel(self, pts: list[tuple[float, float]]) -> list[float]:
        return [v for p in pts for v in (round(p[0] - self.pos[0], 2), round(p[1] - self.pos[1], 2))]

    def moveTo(self, p: tuple[float, float]) -> None:
        q = self._pt(p)
        self.parts.append("m" + join(self._rel([q])) if self.parts else "M" + join([q[0], q[1]]))
        self.pos = self.start = q

    def lineTo(self, p: tuple[float, float]) -> None:
        q = self._pt(p)
        dx, dy = round(q[0] - self.pos[0], 2), round(q[1] - self.pos[1], 2)
        if dx == 0 and dy == 0:
            return
        if dy == 0:
            self.parts.append("h" + join([dx]))
        elif dx == 0:
            self.parts.append("v" + join([dy]))
        else:
            self.parts.append("l" + join([dx, dy]))
        self.pos = q

    def curveTo(self, *pts: tuple[float, float]) -> None:
        qs = [self._pt(p) for p in pts]
        self.parts.append("c" + join(self._rel(qs)))
        self.pos = qs[-1]

    def qCurveTo(self, *pts: tuple[float, float]) -> None:
        qs = [self._pt(p) for p in pts]
        self.parts.append("q" + join(self._rel(qs)))
        self.pos = qs[-1]

    def closePath(self) -> None:
        self.parts.append("z")
        self.pos = self.start

    def endPath(self) -> None:
        pass

    def value(self) -> str:
        return "".join(self.parts)


def svg_d(path: pathops.Path, transform: Matrix) -> str:
    pen = RelPen(transform)
    for verb, pts in path.segments:
        getattr(pen, verb)(*pts)
    return pen.value()


def union(paths: list[pathops.Path]) -> pathops.Path:
    result = pathops.Path()
    for p in paths:
        result = pathops.op(result, p, pathops.PathOp.UNION, fix_winding=True)
    return result


def color_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02x}" for c in rgb)


def layer_groups(fills: list[Fill], key: Any) -> list[tuple[Any, pathops.Path]]:
    """Merge fills with the same style while keeping the painting order of first appearance."""
    order: list[Any] = []
    groups: dict[Any, list[pathops.Path]] = {}
    for f in fills:
        k = key(f)
        if k not in groups:
            order.append(k)
            groups[k] = []
        groups[k].append(f.path)
    return [(k, union(groups[k])) for k in order]


# ---------------------------------------------------------------- metadata


def plist(path: Path) -> Any:
    with path.open("rb") as fh:
        return plistlib.load(fh)


def strings(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8")
    return dict(re.findall(r'"((?:[^"\\]|\\.)+)"\s*=\s*"((?:[^"\\]|\\.)+)"\s*;', text))


def is_localized(name: str) -> bool:
    parts = name.split(".")
    return len(parts) > 1 and parts[-1] in LOCALE_SUFFIXES


def german_terms() -> dict[str, list[str]]:
    data = json.loads((ROOT / "tools" / "keywords_de.json").read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


# Name parts that only describe the style, not the thing ("trash.fill" is no "fill trash").
STYLE_PARTS = {"fill", "slash", "circle", "square", "rectangle", "badge", "and", "inverse", "dashed", "2", "3"}
SPACES = re.compile(r"\s+")


def search_term(word: str) -> str:
    """HA's icon picker turns spaces in the query into "-" ("floor lamp" → "floor-lamp") and compares
    lower-case, so multi-word keywords must be stored the same way to be found."""
    return SPACES.sub("-", word.strip().lower())


def keywords_for(name: str, search: dict[str, list[str]], enhanced: dict[str, list[str]], cats: dict[str, list[str]],
                 de: dict[str, list[str]]) -> list[str]:  # fmt: skip
    words: list[str] = []

    def add(word: str) -> None:
        w = search_term(word)
        if w and w not in words:
            words.append(w)

    for w in [*search.get(name, []), *enhanced.get(name, []), *cats.get(name, [])]:
        add(w)
    parts = name.split(".")
    # natural word order: "lamp.floor" → "floor-lamp" (HA finds "floor lamp" then)
    if len(parts) >= 2 and parts[1] not in STYLE_PARTS:
        add(f"{parts[1]}-{parts[0]}")
    # German terms only from the symbol's own name (parts and leading parts like "lamp.floor"): Apple's
    # keyword lists are too loose for that ("gear" has "tv", "eject" has "trash").
    prefixes = {".".join(parts[:i]) for i in range(2, len(parts) + 1)}
    german: list[str] = []
    for token in {*parts, *prefixes}:
        for g in de.get(token, []):
            g = search_term(g)
            if g not in german and g not in words:
                german.append(g)
    return words + sorted(german)


# ---------------------------------------------------------------- main


def render(names: list[str], workdir: Path) -> None:
    binary = workdir / "render_symbols"
    subprocess.run(
        ["swiftc", "-O", str(ROOT / "tools" / "render_symbols.swift"), "-o", str(binary)],
        check=True,
        capture_output=True,
    )
    (workdir / "names.txt").write_text("\n".join(names), encoding="utf-8")
    subprocess.run([str(binary), str(workdir / "names.txt"), str(workdir), str(RENDER_PT)], check=True)


def iter_pages(workdir: Path, mode: str) -> Iterator[tuple[Interpreter, pymupdf.Page]]:
    doc = pymupdf.open(workdir / f"{mode}.pdf")
    interp = Interpreter(doc)
    for page in doc:
        yield interp, page


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=0, help="only the first N symbols (testing)")
    parser.add_argument("--only", nargs="*", default=[], help="only these symbols (testing)")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if not APP.exists():
        print(f"{APP} not found – install the SF Symbols app first.", file=sys.stderr)
        return 1
    meta_dir = APP / "Contents" / "Resources" / "Metadata"
    availability = plist(meta_dir / "name_availability.plist")
    layersets = plist(meta_dir / "layerset_availability.plist").get("symbols", {})
    search = plist(meta_dir / "symbol_search.plist")
    enhanced_path = APP / "Contents" / "Resources" / "symbols_with_enhanced_keywords.plist"
    enhanced = plist(enhanced_path) if enhanced_path.exists() else {}
    categories = plist(meta_dir / "symbol_categories.plist")
    aliases = {**strings(meta_dir / "legacy_aliases.strings"), **strings(meta_dir / "name_aliases.strings")}
    app_info = plist(APP / "Contents" / "Info.plist")
    de = german_terms()

    names = sorted(availability["symbols"])
    if args.only:
        names = [n for n in names if n in set(args.only)]
    elif args.limit:
        names = names[: args.limit]

    started = time.monotonic()
    mono: dict[str, list[Any]] = {}
    variants: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    unsupported: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        render(names, work)
        # Device space of each page: PDF y goes up. Flip and scale to symbol units.
        heights: dict[int, float] = {}
        mono_paths: dict[str, pathops.Path] = {}
        for i, (interp, page) in enumerate(iter_pages(work, "monochrome")):
            name = names[i]
            heights[i] = page.rect.height
            if page.rect.width <= 1:
                missing.append(name)
                continue
            interp.unsupported = set()
            fills = interp.page_fills(page)
            for feature in interp.unsupported:
                unsupported.setdefault(feature, []).append(name)
            mono_paths[name] = union([f.path for f in fills])
        flip: dict[str, Matrix] = {n: (SCALE, 0.0, 0.0, -SCALE, 0.0, heights[i] * SCALE) for i, n in enumerate(names)}
        for name, path in mono_paths.items():
            x0, y0, x1, y1 = path.bounds
            ax, ay = apply(flip[name], x0, y1)
            bx, by = apply(flip[name], x1, y0)
            box = [round(ax, 2), round(ay, 2), round(bx - ax, 2), round(by - ay, 2)]
            mono[name] = [*box, svg_d(path, flip[name])]
        for mode in ("hierarchical", "multicolor"):
            for i, (interp, page) in enumerate(iter_pages(work, mode)):
                name = names[i]
                if name not in mono or mode not in layersets.get(name, {}):
                    continue
                interp.unsupported = set()
                fills = [f for f in interp.page_fills(page) if f.alpha > 0.001]
                for feature in interp.unsupported:
                    unsupported.setdefault(feature, []).append(f"{name} ({mode})")
                if mode == "hierarchical":
                    groups = layer_groups(fills, lambda f: round(f.alpha, 2))
                    if len(groups) < 2:
                        continue
                    layers = [[k, svg_d(p, flip[name])] for k, p in groups]
                else:
                    groups = layer_groups(fills, lambda f: (color_hex(f.rgb), round(f.alpha, 2)))
                    if all(k[0] == "#000000" for k, _ in groups):
                        continue
                    # black = the symbol's primary colour -> currentColor in the frontend
                    layers = [[k[0] if k[0] != "#000000" else "", k[1], svg_d(p, flip[name])] for k, p in groups]
                variants.setdefault(name, {})["h" if mode == "hierarchical" else "m"] = layers

    # ---- write data
    out: Path = args.out
    for sub in ("m", "v"):
        (out / sub).mkdir(parents=True, exist_ok=True)
        for old in (out / sub).glob("*.json.gz"):
            old.unlink()
    mono_chunks: list[dict[str, Any]] = [{} for _ in range(CHUNKS)]
    var_chunks: list[dict[str, Any]] = [{} for _ in range(CHUNKS)]
    for name, entry in mono.items():
        mono_chunks[chunk_of(name)][name] = entry
    for name, entry in variants.items():
        var_chunks[chunk_of(name)][name] = entry
    alias_count = 0
    for old, new in sorted(aliases.items()):
        target = new
        seen = {old}
        while target not in mono and target in aliases and target not in seen:
            seen.add(target)
            target = aliases[target]
        if old not in mono and target in mono:
            mono_chunks[chunk_of(old)][old] = target
            alias_count += 1
    digest = hashlib.sha256()
    for sub, chunks in (("m", mono_chunks), ("v", var_chunks)):
        for idx, chunk in enumerate(chunks):
            raw = json.dumps(chunk, separators=(",", ":"), sort_keys=True).encode()
            digest.update(raw)
            (out / sub / f"{idx:02x}.json.gz").write_bytes(gzip.compress(raw, 9, mtime=0))
    index = [
        [name, keywords_for(name, search, enhanced, categories, de)] for name in sorted(mono) if not is_localized(name)
    ]
    raw_index = json.dumps(index, separators=(",", ":"), ensure_ascii=False).encode()
    digest.update(raw_index)
    (out / "index.json.gz").write_bytes(gzip.compress(raw_index, 9, mtime=0))
    circle = mono.get("circle")
    meta = {
        "set_version": app_info.get("CFBundleShortVersionString"),
        "app_build": app_info.get("CFBundleVersion"),
        "symbols": len(mono),
        "listed": len(index),
        "aliases": alias_count,
        "hierarchical": sum(1 for v in variants.values() if "h" in v),
        "multicolor": sum(1 for v in variants.values() if "m" in v),
        "missing": missing,
        "chunks": CHUNKS,
        # sf: frame = circle size / 0.85, so plain symbols get MDI-like padding
        "frame": round(max(circle[2], circle[3]) / 0.85, 2) if circle else 24.0,
        "hash": digest.hexdigest()[:12],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(
        f"{len(mono)} symbols ({len(index)} listed, {alias_count} aliases, {meta['hierarchical']} hierarchical, "
        f"{meta['multicolor']} multicolor, {len(missing)} missing) – {size / 1e6:.1f} MB in {out} "
        f"({time.monotonic() - started:.0f} s)"
    )
    if unsupported:
        for feature, where in sorted(unsupported.items()):
            print(f"unsupported PDF feature {feature!r} ignored in {len(where)}: {', '.join(where[:12])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
