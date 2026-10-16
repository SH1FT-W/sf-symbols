"""Zugriff auf die erzeugten Symboldaten (ohne HA, testbar).

Die Daten erzeugt `tools/build_icons.py` aus der lokal installierten SF-Symbols-App:
`data/meta.json` (Satz-Version, Anzahl, Hash), `data/index.json.gz` (Namen + Suchbegriffe),
`data/m/<xx>.json.gz` (einfarbige Pfade) und `data/v/<xx>.json.gz` (Ebenen für hierarchisch/mehrfarbig).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
from typing import Any

# Erlaubte Dateien unter /sf_symbols/<version>/…: Frontend-Modul, Index und die Daten-Stücke.
_DATA_FILE = re.compile(r"^(index|[mv]/[0-9a-f]{2})\.json$")
MODULE_FILE = "sf-symbols.js"


class SymbolDataError(Exception):
    """Die Symboldaten fehlen oder sind beschädigt."""


@dataclass
class SymbolData:
    """Gelesene Metadaten + kleiner Speicher-Cache der ausgelieferten Dateien."""

    data_dir: Path
    frontend_file: Path
    meta: dict[str, Any]
    version: str
    _cache: dict[str, bytes] = field(default_factory=dict, repr=False)

    @property
    def symbol_count(self) -> int:
        return int(self.meta.get("symbols", 0))

    @property
    def set_version(self) -> str:
        return str(self.meta.get("set_version", "?"))

    def module_source(self) -> bytes:
        """Frontend-Modul mit eingesetzten Eckdaten (Rahmen für sf:, Anzahl der Stücke)."""
        if MODULE_FILE not in self._cache:
            config = {
                "frame": self.meta.get("frame", 24),
                "chunks": self.meta.get("chunks", 256),
                "version": self.version,
                "setVersion": self.set_version,
            }
            source = self.frontend_file.read_text(encoding="utf-8")
            self._cache[MODULE_FILE] = source.replace("/*__SF_CONFIG__*/{}", json.dumps(config)).encode()
        return self._cache[MODULE_FILE]

    def data_file(self, path: str) -> bytes | None:
        """Gzip-komprimierter Inhalt einer Datendatei, None bei unbekanntem Pfad."""
        if not _DATA_FILE.match(path):
            return None
        if path not in self._cache:
            file = self.data_dir / f"{path}.gz"
            if not file.is_file():
                return None
            self._cache[path] = file.read_bytes()
        return self._cache[path]


def load_symbol_data(data_dir: Path, frontend_file: Path, integration_version: str) -> SymbolData:
    """Metadaten lesen und die Versions-Kennung für die URLs bilden (blockierend → Executor)."""
    try:
        meta: dict[str, Any] = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
        frontend = frontend_file.read_bytes()
    except (OSError, ValueError) as err:
        raise SymbolDataError(str(err)) from err
    if not meta.get("symbols") or not (data_dir / "m").is_dir():
        raise SymbolDataError("no symbols")
    js_hash = hashlib.sha256(frontend).hexdigest()[:8]
    version = f"{integration_version}-{meta.get('hash', 'x')}-{js_hash}"
    return SymbolData(data_dir=data_dir, frontend_file=frontend_file, meta=meta, version=version)
