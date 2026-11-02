// SF Symbols for Home Assistant – symbol browser (sidebar panel "SF Symbols", admins only).
//
// Lists every symbol of the index with search (Apple's keywords + German terms), switches between the
// "sf:" and "ios:" names and the variants (monochrome / hierarchical / multicolor). A click copies the
// icon name, e.g. "sf:house.fill" or "sf:cloud.sun.fill#multicolor". Only the visible rows are rendered
// (thousands of symbols). The icons are drawn by Home Assistant's own <ha-icon>, so they look exactly
// like on a dashboard; colours come from the active theme's CSS variables.
//
// The data comes from the loader module (same version directory, same symbol files, nothing else).
import "./sf-symbols.js";

export const STYLE_SUFFIX = { "": "", h: "#hierarchical", m: "#multicolor" };
export const MIN_CELL = 88;
export const ROW_HEIGHT = 96;
export const OVERSCAN = 3;

const TEXT = {
  en: {
    search: "Search symbols",
    mono: "Monochrome",
    h: "Hierarchical",
    m: "Multicolor",
    count: (n, total) => (n === total ? `${fmt(total)} symbols` : `${fmt(n)} of ${fmt(total)}`),
    copied: (name) => `Copied ${name}`,
    copyFailed: (name) => `Copy not possible – ${name}`,
    loading: "Loading symbols …",
    failed: "Symbol data not reachable. Reload the page.",
    empty: "No symbol found",
    hint: "Click a symbol to copy its name",
    menu: "Menu",
    clear: "Clear search",
    prefix: "Icon set",
    style: "Variant",
  },
  de: {
    search: "Symbole suchen",
    mono: "Einfarbig",
    h: "Hierarchisch",
    m: "Mehrfarbig",
    count: (n, total) => (n === total ? `${fmt(total)} Symbole` : `${fmt(n)} von ${fmt(total)}`),
    copied: (name) => `${name} kopiert`,
    copyFailed: (name) => `Kopieren nicht möglich – ${name}`,
    loading: "Symbole werden geladen …",
    failed: "Symboldaten nicht erreichbar. Seite neu laden.",
    empty: "Kein Symbol gefunden",
    hint: "Klick auf ein Symbol kopiert den Namen",
    menu: "Menü",
    clear: "Suche leeren",
    prefix: "Symbolsatz",
    style: "Variante",
  },
};

let numberFormat = null;
function fmt(n) {
  try {
    numberFormat ??= new Intl.NumberFormat();
    return numberFormat.format(n);
  } catch (e) {
    return String(n);
  }
}

export function textFor(language) {
  return TEXT[String(language || "").slice(0, 2)] || TEXT.en;
}

/** Name as written in the icon set: "ios:" uses "-" where Apple uses ".". */
export function displayName(prefix, name) {
  return prefix === "ios" ? name.replace(/\./g, "-") : name;
}

/** Full icon string for dashboards/entities, e.g. "sf:cloud.sun.fill#multicolor". */
export function iconName(prefix, name, style = "") {
  return `${prefix}:${displayName(prefix, name)}${STYLE_SUFFIX[style] || ""}`;
}

/**
 * Search entries from the "sf:" picker list ({name, keywords}; keywords already contain the name
 * parts). `parts` = name parts, `words` = name parts, keywords and the words of multi-word keywords
 * ("floor-lamp" → "floor", "lamp").
 */
export function buildEntries(list) {
  return list.map(({ name, keywords = [] }) => {
    const parts = name.split(".");
    const words = new Set(parts);
    for (const k of keywords) {
      words.add(k);
      if (k.includes("-")) for (const w of k.split("-")) if (w) words.add(w);
    }
    return { name, parts, words: [...words] };
  });
}

/** Lower case, without "sf:"/"ios:" and "#variant", "-"/"_"/spaces as Apple's ".". */
export function normalizeQuery(query) {
  let q = String(query || "").trim().toLowerCase();
  q = q.replace(/^(sf|ios):/, "");
  const hash = q.indexOf("#");
  if (hash >= 0) q = q.slice(0, hash);
  return q.replace(/[\s\-_]+/g, ".").replace(/\.{2,}/g, ".").replace(/^\.|\.$/g, "");
}

/**
 * Filters and ranks: exact name, name prefix, every word starts a name part, name contains the
 * query, every word starts a keyword. Within a rank shorter names first, then index order.
 * `allowed` (Set of names) limits the result, e.g. to symbols with a multicolor variant.
 */
export function searchEntries(entries, query, allowed = null) {
  const q = normalizeQuery(query);
  const pool = allowed ? entries.filter((e) => allowed.has(e.name)) : entries;
  if (!q) return pool;
  const tokens = q.split(".");
  const starts = (list) => tokens.every((t) => list.some((w) => w.startsWith(t)));
  const hits = [];
  for (let i = 0; i < pool.length; i++) {
    const e = pool[i];
    let rank;
    if (e.name === q) rank = 0;
    else if (e.name.startsWith(q)) rank = 1;
    else if (starts(e.parts)) rank = 2;
    else if (e.name.includes(q)) rank = 3;
    else if (starts(e.words)) rank = 4;
    else continue;
    hits.push({ rank, len: e.name.length, i });
  }
  hits.sort((a, b) => a.rank - b.rank || a.len - b.len || a.i - b.i);
  return hits.map((h) => pool[h.i]);
}

/**
 * Visible part of the grid in its own coordinates: the scroller's box cut to the window (whichever of
 * the two scrolls), relative to the grid's top. Rects as from getBoundingClientRect().
 */
export function visibleWindow(gridRect, scrollerRect, windowHeight) {
  const top = Math.max(scrollerRect.top, 0);
  const bottom = Math.min(scrollerRect.bottom, windowHeight);
  return { top: top - gridRect.top, height: Math.max(0, bottom - top) };
}

/** Columns, cell width and total height of the grid for a given inner width. */
export function gridMetrics(width, count, minCell = MIN_CELL, rowHeight = ROW_HEIGHT) {
  const cols = Math.max(1, Math.floor(width / minCell));
  const rows = Math.ceil(count / cols);
  return { cols, cellWidth: width / cols, rows, height: rows * rowHeight };
}

/** Indexes [start, end) to render for a scroll position, plus `overscan` rows above and below. */
export function visibleRange(scrollTop, viewport, cols, count, rowHeight = ROW_HEIGHT, overscan = OVERSCAN) {
  const first = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const last = Math.max(0, Math.ceil((scrollTop + viewport) / rowHeight)) + overscan;
  return { start: Math.min(count, first * cols), end: Math.min(count, last * cols) };
}

/**
 * Copies text. navigator.clipboard needs a secure context (https/localhost); Home Assistant is often
 * reached over plain http in the LAN, so fall back to a hidden textarea + execCommand("copy").
 */
export async function copyText(text, nav = globalThis.navigator, doc = globalThis.document) {
  try {
    if (nav?.clipboard?.writeText) {
      await nav.clipboard.writeText(text);
      return true;
    }
  } catch (e) {
    /* fall through to the textarea */
  }
  let area = null;
  try {
    area = doc.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "0";
    area.style.opacity = "0";
    doc.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, text.length); // iOS selects nothing with select() alone
    return Boolean(doc.execCommand("copy"));
  } catch (e) {
    return false;
  } finally {
    area?.remove?.();
  }
}

const STORE_KEY = "sf-symbols-panel";

function loadPrefs() {
  try {
    const p = JSON.parse(globalThis.localStorage?.getItem(STORE_KEY) || "{}");
    return { prefix: p.prefix === "ios" ? "ios" : "sf", style: Object.hasOwn(STYLE_SUFFIX, p.style) ? p.style : "" };
  } catch (e) {
    return { prefix: "sf", style: "" };
  }
}

function savePrefs(prefs) {
  try {
    globalThis.localStorage?.setItem(STORE_KEY, JSON.stringify(prefs));
  } catch (e) {
    /* private mode: just not remembered */
  }
}

const MENU_PATH = "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z";
const SEARCH_PATH =
  "M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z";
const CLOSE_PATH =
  "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z";
const svg = (d) => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"></path></svg>`;

const STYLE = `
:host {
  /* Home Assistant's panel container has no fixed height: take the viewport, the grid scrolls inside.
     The container already pads the safe areas (top/bottom insets), so leave them out here. */
  display: block;
  height: calc(100vh - var(--safe-area-inset-top, 0px) - var(--safe-area-inset-bottom, 0px));
  height: calc(100dvh - var(--safe-area-inset-top, 0px) - var(--safe-area-inset-bottom, 0px));
  background: var(--primary-background-color, #fafafa);
  color: var(--primary-text-color, #212121);
  font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif));
  -webkit-font-smoothing: antialiased;
}
.root { display: flex; flex-direction: column; height: 100%; position: relative; }
header {
  display: flex; align-items: center; gap: 4px; flex: none;
  height: var(--header-height, 56px); padding: 0 12px;
  background: var(--app-header-background-color, var(--primary-color, #03a9f4));
  color: var(--app-header-text-color, #fff);
  border-bottom: var(--app-header-border-bottom, none);
  box-sizing: border-box;
}
header .title { font-size: 20px; font-weight: 400; margin-left: 12px; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.icon-btn {
  width: 40px; height: 40px; border: none; border-radius: 50%; background: none; color: inherit;
  display: inline-flex; align-items: center; justify-content: center; cursor: pointer; padding: 0;
}
.icon-btn:hover { background: rgba(127, 127, 127, 0.15); }
.icon-btn svg { width: 24px; height: 24px; fill: currentColor; }
.menu[hidden] { display: none; }
.controls {
  flex: none; display: flex; flex-direction: column; gap: 10px;
  padding: 12px 16px 10px; max-width: 1200px; width: 100%; margin: 0 auto; box-sizing: border-box;
}
.search {
  display: flex; align-items: center; gap: 8px; height: 44px; padding: 0 4px 0 12px;
  border-radius: 22px; background: var(--card-background-color, #fff);
  border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)); box-sizing: border-box;
}
.search:focus-within { border-color: var(--primary-color, #03a9f4); }
.search > svg { width: 22px; height: 22px; fill: var(--secondary-text-color, #727272); flex: none; }
.search input {
  flex: 1; min-width: 0; height: 100%; border: none; outline: none; background: none;
  color: var(--primary-text-color, #212121); font: inherit; font-size: 16px;
}
.search input::-webkit-search-cancel-button { display: none; }
.search .clear { width: 36px; height: 36px; color: var(--secondary-text-color, #727272); }
.search .clear[hidden] { display: none; }
.row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.seg {
  display: inline-flex; border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)); border-radius: 18px;
  overflow: hidden; background: var(--card-background-color, #fff);
}
.seg button {
  border: none; background: none; color: var(--primary-text-color, #212121); font: inherit; font-size: 14px;
  height: 34px; padding: 0 14px; cursor: pointer; white-space: nowrap;
}
.seg button + button { border-left: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)); }
.seg button[aria-pressed="true"] {
  background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff);
}
.seg button:disabled { opacity: 0.4; cursor: default; }
.count { font-size: 13px; color: var(--secondary-text-color, #727272); margin-left: auto; white-space: nowrap; }
.scroller {
  flex: 1; min-height: 0; overflow-y: auto; overflow-x: hidden; -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
}
.inner { max-width: 1200px; margin: 0 auto; padding: 0 16px 24px; box-sizing: border-box; }
.sizer { position: relative; contain: strict; }
.cell {
  position: absolute; top: 0; left: 0; box-sizing: border-box; padding: 10px 4px 6px;
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  border: none; border-radius: 12px; background: none; color: var(--primary-text-color, #212121);
  font: inherit; cursor: pointer; -webkit-tap-highlight-color: transparent;
}
.cell:hover, .cell:focus-visible { background: var(--secondary-background-color, rgba(127, 127, 127, 0.12)); outline: none; }
.cell:active { background: rgba(127, 127, 127, 0.22); }
.cell.done { box-shadow: inset 0 0 0 2px var(--primary-color, #03a9f4); }
.cell ha-icon { --mdc-icon-size: 32px; width: 32px; height: 32px; flex: none; color: var(--primary-text-color, #212121); }
.cell .label {
  font-size: 11px; line-height: 14px; color: var(--secondary-text-color, #727272); text-align: center;
  width: 100%; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow-wrap: anywhere;
}
.message { text-align: center; color: var(--secondary-text-color, #727272); padding: 48px 16px; }
.message[hidden] { display: none; }
.toast {
  position: absolute; left: 50%; bottom: 24px;
  transform: translate(-50%, 16px); opacity: 0; pointer-events: none; transition: opacity 0.15s, transform 0.15s;
  background: var(--primary-text-color, #212121); color: var(--card-background-color, #fff);
  padding: 10px 18px; border-radius: 22px; font-size: 14px; max-width: calc(100% - 48px);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}
.toast.show { opacity: 1; transform: translate(-50%, 0); }
@media (max-width: 600px) {
  .controls { padding: 10px 12px 8px; }
  .inner { padding: 0 8px 24px; }
  .seg button { padding: 0 11px; font-size: 13px; }
  .count { width: 100%; margin-left: 0; }
}
`;

const ConstructorBase = typeof HTMLElement === "undefined" ? class {} : HTMLElement;

export class SFSymbolsPanel extends ConstructorBase {
  constructor() {
    super();
    this._prefs = loadPrefs();
    this._entries = null;
    this._variants = null;
    this._shown = [];
    this._query = "";
    this._cells = new Map(); // index → cell element
    this._pool = [];
    this._metrics = null;
    this._frame = 0;
    this._narrow = false;
    this._text = TEXT.en;
  }

  set hass(hass) {
    // menu button like HA's own ha-menu-button: also when the sidebar is hidden completely, never in
    // kiosk mode or when the Companion app brings its own sidebar
    this._sidebarHidden = hass?.dockedSidebar === "always_hidden";
    this._noMenu = Boolean(hass?.kioskMode || hass?.auth?.external?.config?.hasSidebar);
    this._syncMenu();
    const text = textFor(hass?.locale?.language || hass?.language);
    if (text !== this._text) {
      this._text = text;
      if (this.shadowRoot) this._applyText();
    }
  }

  set narrow(value) {
    this._narrow = Boolean(value);
    this._syncMenu();
  }

  _syncMenu() {
    const menu = this.shadowRoot?.querySelector(".menu");
    if (menu) menu.hidden = this._noMenu || !(this._narrow || this._sidebarHidden);
  }

  connectedCallback() {
    if (!this.shadowRoot) this._build();
    this._resize ??= new ResizeObserver(() => this._layout());
    this._resize.observe(this._scroller);
    // in case the page itself scrolls (the panel taller than the window), follow that as well
    this._onWindowScroll ??= () => this._schedule();
    globalThis.addEventListener?.("scroll", this._onWindowScroll, { passive: true });
    // keep every data chunk while the browser is open (see widenCache), normal limit again afterwards
    this._restoreCache ??= globalThis.sfSymbols?.api?.widenCache?.();
    if (!this._entries) this._load();
  }

  disconnectedCallback() {
    this._restoreCache?.();
    this._restoreCache = undefined;
    this._resize?.disconnect();
    globalThis.removeEventListener?.("scroll", this._onWindowScroll);
  }

  _build() {
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>${STYLE}</style>
      <div class="root">
        <header>
          <button class="icon-btn menu" hidden>${svg(MENU_PATH)}</button>
          <div class="title">SF Symbols</div>
        </header>
        <div class="controls">
          <label class="search">${svg(SEARCH_PATH)}
            <input type="search" autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search">
            <button class="icon-btn clear" hidden>${svg(CLOSE_PATH)}</button>
          </label>
          <div class="row">
            <div class="seg prefix" role="group">
              <button data-value="sf">sf:</button><button data-value="ios">ios:</button>
            </div>
            <div class="seg style" role="group">
              <button data-value=""></button><button data-value="h"></button><button data-value="m"></button>
            </div>
            <span class="count"></span>
          </div>
        </div>
        <div class="scroller"><div class="inner">
          <div class="message"></div>
          <div class="sizer"></div>
        </div></div>
        <div class="toast" role="status" aria-live="polite"></div>
      </div>`;
    this._scroller = root.querySelector(".scroller");
    this._sizer = root.querySelector(".sizer");
    this._input = root.querySelector("input");
    this._message = root.querySelector(".message");
    this._count = root.querySelector(".count");
    this._toast = root.querySelector(".toast");
    this._syncMenu();
    root.querySelector(".menu").addEventListener("click", () => {
      // same event as Home Assistant's own <ha-menu-button>: opens the sidebar on phones
      this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
    });
    const clear = root.querySelector(".clear");
    this._input.addEventListener("input", () => {
      clear.hidden = !this._input.value;
      clearTimeout(this._debounce);
      this._debounce = setTimeout(() => this._setQuery(this._input.value), 80);
    });
    clear.addEventListener("click", (ev) => {
      ev.preventDefault();
      this._input.value = "";
      clear.hidden = true;
      this._setQuery("");
      this._input.focus();
    });
    for (const group of ["prefix", "style"]) {
      root.querySelector(`.seg.${group}`).addEventListener("click", (ev) => {
        const btn = ev.target.closest("button");
        if (!btn || btn.disabled) return;
        this._prefs[group] = btn.dataset.value;
        savePrefs(this._prefs);
        this._syncButtons();
        if (group === "style") this._filter(true);
        else this._refreshCells();
      });
    }
    this._sizer.addEventListener("click", (ev) => {
      const cell = ev.target.closest(".cell");
      if (cell) this._copy(cell);
    });
    this._scroller.addEventListener("scroll", () => this._schedule(), { passive: true });
    this._applyText();
    this._syncButtons();
  }

  _applyText() {
    const t = this._text;
    const root = this.shadowRoot;
    this._input.placeholder = t.search;
    root.querySelector(".menu").setAttribute("aria-label", t.menu);
    root.querySelector(".clear").setAttribute("aria-label", t.clear);
    root.querySelector(".seg.prefix").setAttribute("aria-label", t.prefix);
    root.querySelector(".seg.style").setAttribute("aria-label", t.style);
    const [mono, h, m] = root.querySelectorAll(".seg.style button");
    mono.textContent = t.mono;
    h.textContent = t.h;
    m.textContent = t.m;
    this._updateCount();
    if (!this._entries) this._message.textContent = this._failed ? t.failed : t.loading;
    else this._message.textContent = t.empty;
  }

  _syncButtons() {
    for (const group of ["prefix", "style"]) {
      for (const btn of this.shadowRoot.querySelectorAll(`.seg.${group} button`)) {
        btn.setAttribute("aria-pressed", String(btn.dataset.value === this._prefs[group]));
        if (group === "style" && btn.dataset.value) btn.disabled = !this._variants;
      }
    }
  }

  async _load() {
    const api = globalThis.sfSymbols?.api;
    try {
      if (!api) throw new Error("SF Symbols module not loaded");
      const [list, variants] = await Promise.all([api.getIconList("sf"), (api.getVariants?.() ?? Promise.reject(new Error("old module"))).catch(() => null)]);
      this._entries = buildEntries(list);
      this._variants = variants ? { h: new Set(variants.h), m: new Set(variants.m) } : null;
    } catch (err) {
      this._failed = true;
      this._message.textContent = this._text.failed;
      globalThis.console?.warn(`SF Symbols panel: ${err?.message || err}`);
      return;
    }
    if (!this._variants) this._prefs.style = "";
    this._syncButtons();
    this._message.textContent = this._text.empty;
    this._filter(true);
  }

  _setQuery(query) {
    if (query === this._query) return;
    this._query = query;
    this._filter(true);
  }

  _filter(toTop) {
    if (!this._entries) return;
    const allowed = this._prefs.style && this._variants ? this._variants[this._prefs.style] : null;
    this._shown = searchEntries(this._entries, this._query, allowed);
    this._message.hidden = this._shown.length > 0;
    this._updateCount();
    if (toTop) this._scroller.scrollTop = 0;
    this._refreshCells();
  }

  _updateCount() {
    if (!this._entries || !this._count) return;
    const t = this._text;
    this._count.textContent = `${t.count(this._shown.length, this._entries.length)} · ${t.hint}`;
  }

  /** Drop every rendered cell (names or variant changed), then draw the visible rows again. */
  _refreshCells() {
    for (const cell of this._cells.values()) this._release(cell);
    this._cells.clear();
    this._layout();
  }

  _layout() {
    if (!this._entries) return;
    const width = this._sizer.clientWidth;
    if (!width) return;
    this._metrics = gridMetrics(width, this._shown.length);
    this._sizer.style.height = `${this._metrics.height}px`;
    this._render(true);
  }

  _schedule() {
    if (this._frame) return;
    this._frame = requestAnimationFrame(() => {
      this._frame = 0;
      this._render(false);
    });
  }

  _release(cell) {
    cell.remove();
    this._pool.push(cell);
  }

  _render(relayout) {
    const m = this._metrics;
    if (!m) return;
    const view = visibleWindow(
      this._sizer.getBoundingClientRect(),
      this._scroller.getBoundingClientRect(),
      globalThis.innerHeight || this._scroller.clientHeight
    );
    const { start, end } = visibleRange(view.top, view.height, m.cols, this._shown.length);
    for (const [i, cell] of this._cells) {
      if (i < start || i >= end) {
        this._release(cell);
        this._cells.delete(i);
      }
    }
    const { prefix, style } = this._prefs;
    for (let i = start; i < end; i++) {
      let cell = this._cells.get(i);
      if (!cell) {
        cell = this._pool.pop() || this._makeCell();
        const entry = this._shown[i];
        const icon = iconName(prefix, entry.name, style);
        cell.dataset.icon = icon;
        cell.title = icon;
        cell.firstChild.icon = icon;
        // allow line breaks after each "." / "-" of long names
        cell.lastChild.textContent = displayName(prefix, entry.name).replace(/([.-])/g, "$1​");
        clearTimeout(cell._doneTimer);
        cell.classList.remove("done");
        this._sizer.appendChild(cell);
        this._cells.set(i, cell);
        relayout = true;
      }
      if (relayout) {
        const row = Math.floor(i / m.cols);
        const col = i % m.cols;
        cell.style.width = `${m.cellWidth}px`;
        cell.style.height = `${ROW_HEIGHT}px`;
        cell.style.transform = `translate(${col * m.cellWidth}px, ${row * ROW_HEIGHT}px)`;
      }
    }
  }

  _makeCell() {
    const cell = document.createElement("button");
    cell.className = "cell";
    cell.appendChild(document.createElement("ha-icon"));
    const label = document.createElement("span");
    label.className = "label";
    cell.appendChild(label);
    return cell;
  }

  async _copy(cell) {
    const name = cell.dataset.icon;
    // mark before the await: the cell may be reused for another symbol while copying
    cell.classList.add("done");
    clearTimeout(cell._doneTimer);
    cell._doneTimer = setTimeout(() => cell.classList.remove("done"), 1200);
    const ok = await copyText(name, globalThis.navigator, document);
    if (!ok && cell.dataset.icon === name) cell.classList.remove("done");
    this._showToast(ok ? this._text.copied(name) : this._text.copyFailed(name));
  }

  _showToast(message) {
    this._toast.textContent = message;
    this._toast.classList.add("show");
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => this._toast.classList.remove("show"), 1800);
  }
}

if (typeof window !== "undefined" && window.customElements && !window.customElements.get("sf-symbols-panel")) {
  window.customElements.define("sf-symbols-panel", SFSymbolsPanel);
}
