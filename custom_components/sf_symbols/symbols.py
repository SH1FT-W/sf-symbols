"""Access to the generated symbol data (without HA, testable).

`tools/build_icons.py` creates the data from the locally installed SF Symbols app:
`data/meta.json` (set version, count, hash), `data/index.json.gz` (names + search terms),
`data/m/<xx>.json.gz` (monochrome paths) and `data/v/<xx>.json.gz` (layers for hierarchical/multicolor).
`variants.json` is derived from the `v/` chunks on first request (which symbols have which variant).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import gzip
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Allowed files under /sf_symbols/<version>/…: index, variant list and the data chunks.
_DATA_FILE = re.compile(r"^(index|variants|[mv]/[0-9a-f]{2})\.json$")
MODULE_FILE = "sf-symbols.js"
# symbol browser (sidebar panel); public like the loader module, it contains no symbols
PANEL_FILE = "sf-symbols-panel.js"
VARIANTS_FILE = "variants.json"


def is_data_file(path: str) -> bool:
    """index.json, variants.json, m/xx.json or v/xx.json (not the modules, no other paths)."""
    return bool(_DATA_FILE.match(path))


def build_variants(data_dir: Path) -> dict[str, list[str]]:
    """Names with a hierarchical ("h") or multicolor ("m") variant, read from the v/ chunks (blocking)."""
    found: dict[str, list[str]] = {"h": [], "m": []}
    for file in sorted((data_dir / "v").glob("*.json.gz")):
        chunk: dict[str, dict[str, Any]] = json.loads(gzip.decompress(file.read_bytes()))
        for name, variants in chunk.items():
            for key, names in found.items():
                if key in variants:
                    names.append(name)
    for names in found.values():
        names.sort()
    return found


class SymbolDataError(Exception):
    """The symbol data is missing or damaged."""


@dataclass
class SymbolData:
    """Read metadata + small in-memory cache of the served files."""

    data_dir: Path
    frontend_file: Path
    meta: dict[str, Any]
    version: str
    # module sources as hashed at load time: the URL version always matches the served content
    frontend_source: bytes = field(repr=False)
    panel_source: bytes = field(default=b"", repr=False)
    _cache: dict[str, bytes] = field(default_factory=dict, repr=False)

    @property
    def symbol_count(self) -> int:
        return int(self.meta.get("symbols", 0))

    @property
    def set_version(self) -> str:
        return str(self.meta.get("set_version", "?"))

    def cached(self, path: str) -> bytes | None:
        """Content already read (no file access, safe in the event loop)."""
        return self._cache.get(path)

    def load(self, path: str) -> bytes | None:
        """Read and remember a module or data file (blocking → executor)."""
        if path == MODULE_FILE:
            return self.module_source()
        if path == PANEL_FILE:
            self._cache[PANEL_FILE] = self.panel_source
            return self.panel_source
        return self.data_file(path)

    def module_source(self) -> bytes:
        """Frontend module with the inserted settings (frame for sf:, chunk count), without reading the file again."""
        if MODULE_FILE not in self._cache:
            config = {
                "frame": self.meta.get("frame", 24),
                "chunks": self.meta.get("chunks", 256),
                "version": self.version,
                "setVersion": self.set_version,
            }
            source = self.frontend_source.decode("utf-8")
            self._cache[MODULE_FILE] = source.replace("/*__SF_CONFIG__*/{}", json.dumps(config)).encode()
        return self._cache[MODULE_FILE]

    def data_file(self, path: str) -> bytes | None:
        """Gzip-compressed content of a data file, None for an unknown path."""
        if not is_data_file(path):
            return None
        if path not in self._cache:
            file = self.data_dir / f"{path}.gz"
            try:
                if path == VARIANTS_FILE:
                    variants = json.dumps(build_variants(self.data_dir), separators=(",", ":"))
                    self._cache[path] = gzip.compress(variants.encode(), mtime=0)
                else:
                    self._cache[path] = file.read_bytes()
            except FileNotFoundError:
                return None
            except (OSError, ValueError) as err:
                # damaged/unreadable file: 404 instead of a server error, the next request tries again
                _LOGGER.warning("SF Symbols: cannot read %s: %s", file.name, err)
                return None
        return self._cache[path]


def load_symbol_data(data_dir: Path, frontend_file: Path, integration_version: str) -> SymbolData:
    """Read the metadata and build the version id for the URLs (blocking → executor).

    The panel module sits next to the loader module (same directory, `PANEL_FILE`).
    """
    try:
        meta: dict[str, Any] = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
        frontend = frontend_file.read_bytes()
        panel = (frontend_file.parent / PANEL_FILE).read_bytes()
    except (OSError, ValueError) as err:
        raise SymbolDataError(str(err)) from err
    if not meta.get("symbols") or not (data_dir / "m").is_dir():
        raise SymbolDataError("no symbols")
    js_hash = hashlib.sha256(frontend + b"\0" + panel).hexdigest()[:8]
    version = f"{integration_version}-{meta.get('hash', 'x')}-{js_hash}"
    return SymbolData(
        data_dir=data_dir,
        frontend_file=frontend_file,
        meta=meta,
        version=version,
        frontend_source=frontend,
        panel_source=panel,
    )
