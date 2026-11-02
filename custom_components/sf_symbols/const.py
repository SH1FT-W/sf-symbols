"""Constants of the SF Symbols integration."""

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
# one year; the URL changes with every new symbol set or frontend state
CACHE_IMMUTABLE: Final = "public, max-age=31536000, immutable"
# symbol data: only the logged-in user's browser keeps it (no shared caches/proxies)
CACHE_IMMUTABLE_PRIVATE: Final = "private, max-age=31536000, immutable"

# Symbol browser in the sidebar (admins only: only they can set icons on entities and dashboards)
CONF_SHOW_PANEL: Final = "show_panel"
DEFAULT_SHOW_PANEL: Final = True
PANEL_URL_PATH: Final = "sf-symbols"
PANEL_ELEMENT: Final = "sf-symbols-panel"
PANEL_TITLE: Final = "SF Symbols"
PANEL_ICON: Final = "mdi:shape-outline"
