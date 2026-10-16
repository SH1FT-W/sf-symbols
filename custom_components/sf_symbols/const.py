"""Konstanten der SF-Symbols-Integration."""

from __future__ import annotations

from pathlib import Path
from typing import Final

DOMAIN: Final = "sf_symbols"
URL_BASE: Final = f"/{DOMAIN}"
PACKAGE_DIR: Final = Path(__file__).parent
DATA_DIR: Final = PACKAGE_DIR / "data"
FRONTEND_FILE: Final = PACKAGE_DIR / "frontend" / "sf-symbols.js"
CUPERTINO_DOMAIN: Final = "cupertino"
ISSUE_CUPERTINO: Final = "cupertino_installed"
# ein Jahr; die URL ändert sich bei jedem neuen Symbolsatz bzw. Frontend-Stand
CACHE_IMMUTABLE: Final = "public, max-age=31536000, immutable"
# Symboldaten: nur der Browser des angemeldeten Nutzers speichert sie (keine geteilten Caches/Proxys)
CACHE_IMMUTABLE_PRIVATE: Final = "private, max-age=31536000, immutable"
