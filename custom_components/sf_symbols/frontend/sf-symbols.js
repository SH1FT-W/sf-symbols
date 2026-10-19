// SF Symbols for Home Assistant – icon sets "sf:" (Apple names, sf:lamp.floor) and
// "ios:" (Cupertino Icons compatible, ios:lamp-floor).
//
// Variants after "#": hierarchical (h) and multicolor (m), e.g. sf:cloud.sun.fill#multicolor.
// Unknown suffixes (Cupertino's #color, #invert, #fullcolor …) fall back to monochrome, which is
// what Cupertino effectively drew for them.
//
// This module is public; the data is not: /sf_symbols/<version>/m/<xx>.json (outlines),
// v/<xx>.json (layers) and index.json (picker list) need the logged-in user's token, which the
// module takes from Home Assistant's frontend (window.hassConnection / <home-assistant>.hass.auth).
// The server inserts the config below; the version in the URL changes with every data/module update.

const CONFIG = /*__SF_CONFIG__*/{};
const CHUNKS = CONFIG.chunks || 256;
const FRAME = CONFIG.frame || 24;
const SVG_NS = "http://www.w3.org/2000/svg";
// Marks the path of a layered variant, so the ha-svg-icon hook can tell it apart from the
// plain outline (zero-area subpaths, invisible).
const MARK = { h: "M0 0z", m: "M0 0zM0 0z" };
const VARIANTS = { hierarchical: "h", h: "h", multicolor: "m", m: "m" };
// Memory limits: decoded chunks are large (≈ 37 symbols each), layer info is per painted icon.
export const MAX_CHUNKS = 48;
export const MAX_LAYERS = 600;

export function fnv1a(text) {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

export function chunkOf(name, chunks = CHUNKS) {
  return (fnv1a(name) % chunks).toString(16).padStart(2, "0");
}

/** Map with a size limit; reading an entry makes it "recent", the oldest entry goes first. */
export class Lru extends Map {
  constructor(max) {
    super();
    this.max = max;
  }

  get(key) {
    if (!super.has(key)) return undefined;
    const value = super.get(key);
    super.delete(key);
    super.set(key, value);
    return value;
  }

  set(key, value) {
    if (super.has(key)) super.delete(key);
    super.set(key, value);
    while (this.size > this.max) super.delete(this.keys().next().value);
    return this;
  }
}

/** "ios:" names use "-" where Apple uses "." (lamp-floor → lamp.floor). Apple names never contain "-". */
export function canonical(prefix, name) {
  return prefix === "ios" ? name.replace(/-/g, ".") : name;
}

export function parseIcon(prefix, icon) {
  const hash = icon.indexOf("#");
  const base = hash < 0 ? icon : icon.slice(0, hash);
  const suffix = hash < 0 ? "" : icon.slice(hash + 1).toLowerCase();
  return { name: canonical(prefix, base), variant: VARIANTS[suffix] || "" };
}

const r2 = (v) => Math.round(v * 100) / 100;

/**
 * Where a symbol sits: "ios:" keeps Cupertino's tight box. "sf:" always gets the same square of
 * side `frame` (centred on the symbol), so all symbols share one scale and stroke weight. The few
 * symbols larger than the square (wide text/car symbols) are scaled down into it: `scale` < 1.
 */
export function fitFor(prefix, [x, y, w, h], frame = FRAME) {
  if (prefix === "ios") return { viewBox: `${x} ${y} ${w} ${h}`, scale: 1, ox: 0, oy: 0 };
  const cx = x + w / 2;
  const cy = y + h / 2;
  const scale = Math.min(1, frame / Math.max(w, h));
  return {
    viewBox: `${r2(cx - frame / 2)} ${r2(cy - frame / 2)} ${r2(frame)} ${r2(frame)}`,
    scale,
    // scaling around the centre: p' = p·scale + c·(1 − scale)
    ox: cx * (1 - scale),
    oy: cy * (1 - scale),
  };
}

export function viewBoxFor(prefix, box, frame = FRAME) {
  return fitFor(prefix, box, frame).viewBox;
}

const PATH_TOKEN = /([A-Za-z])|[\s,]*(-?(?:\d+(?:\.\d+)?|\.\d+))/g;

/**
 * Scales path data from build_icons.py (absolute "M x y" per subpath start, everything else
 * relative) by `k` around the offset (ox, oy).
 */
export function scalePath(d, k, ox = 0, oy = 0) {
  if (k === 1) return d;
  let cmd = "";
  let arg = 0;
  return d.replace(PATH_TOKEN, (_m, letter, num) => {
    if (letter) {
      cmd = letter;
      arg = 0;
      return letter;
    }
    const i = arg++;
    const v = r2(cmd === "M" && i < 2 ? Number(num) * k + (i === 0 ? ox : oy) : Number(num) * k);
    // separator only where needed: not right after the command letter, not before a minus sign
    return i === 0 || v < 0 ? String(v) : ` ${v}`;
  });
}

/** Turns stored layers into {path, secondaryPath, layers} (secondaryPath = HA's own fallback). */
export function layered(variant, layers, mark = MARK[variant], fit = (d) => d) {
  const out = [];
  let primary = "";
  let secondary = "";
  for (const layer of layers) {
    if (variant === "h") {
      const [opacity, raw] = layer;
      const d = fit(raw);
      out.push({ d, opacity, fill: "" });
      if (opacity >= 1) primary += d;
      else secondary += d;
    } else {
      const [color, opacity, raw] = layer;
      const d = fit(raw);
      // Apple-Weiß wäre im hellen Design unsichtbar → Textfarbe (Apple-Weiß: --sf-symbols-white: #fff setzen)
      const fill = color === "#ffffff" ? "var(--sf-symbols-white, var(--primary-text-color))" : color;
      out.push({ d, opacity, fill });
      if (!color) primary += d;
      else secondary += d;
    }
  }
  return { path: primary + mark, secondaryPath: secondary || undefined, layers: out };
}

export function createSFSymbols({ base, fetchJson, warn = () => {} }) {
  const chunks = new Lru(MAX_CHUNKS);
  const layers = new Lru(MAX_LAYERS);
  const warned = new Set();
  const lists = {};
  let index = null;

  const chunk = (kind, idx) => {
    const key = `${kind}/${idx}`;
    let p = chunks.get(key);
    if (!p) {
      p = fetchJson(`${base}${key}.json`).catch((err) => {
        chunks.delete(key);
        throw err;
      });
      chunks.set(key, p);
    }
    return p;
  };

  const outline = async (name, depth = 0) => {
    const entry = (await chunk("m", chunkOf(name)))[name];
    if (typeof entry === "string" && depth < 3) return outline(entry, depth + 1); // renamed symbol
    return Array.isArray(entry) ? { name, entry } : null;
  };

  const getIcon = async (prefix, icon) => {
    const { name, variant } = parseIcon(prefix, icon);
    let found;
    try {
      found = await outline(name);
    } catch (err) {
      // data not reachable (offline, token rejected): draw nothing, try again next time, say so once
      if (!warned.has("fetch")) {
        warned.add("fetch");
        warn(`SF Symbols: icon data not reachable (${err?.message || err})`);
      }
      return {};
    }
    if (!found) {
      if (!warned.has(`${prefix}:${name}`)) {
        warned.add(`${prefix}:${name}`);
        warn(`SF Symbols: unknown icon ${prefix}:${icon}`);
      }
      return {};
    }
    const [x, y, w, h, d] = found.entry;
    const { viewBox, scale, ox, oy } = fitFor(prefix, [x, y, w, h]);
    const fit = (p) => scalePath(p, scale, ox, oy);
    if (variant) {
      const vars = (await chunk("v", chunkOf(found.name)).catch(() => ({})))[found.name];
      if (vars?.[variant]) {
        const icn = layered(variant, vars[variant], MARK[variant], fit);
        layers.set(icn.path, icn.layers);
        return { path: icn.path, secondaryPath: icn.secondaryPath, viewBox };
      }
    }
    return { path: fit(d), viewBox };
  };

  /**
   * Picker list. HA searches name parts (split at "-"), then keywords, then the full id. Keywords
   * only go to "sf:" (plus its name parts, so "lamp" ranks as a keyword hit): the "ios:" list keeps
   * every Cupertino name (Casora checks it for "-fill"/"-inverse"), but without keywords, so German
   * or English search terms show each symbol once instead of a flood of "ios:" duplicates.
   */
  const getIconList = async (prefix) => {
    if (!index) {
      index = fetchJson(`${base}index.json`).catch((err) => {
        index = null;
        throw err;
      });
    }
    const data = await index;
    if (!lists[prefix]) {
      lists[prefix] =
        prefix === "ios"
          ? data.map(([name]) => ({ name: name.replace(/\./g, "-") }))
          : data.map(([name, keywords]) => ({ name, keywords: [...name.split("."), ...keywords] }));
    }
    return lists[prefix];
  };

  return { getIcon, getIconList, layers };
}

/** Logged-in user's auth object (home-assistant-js-websocket Auth / Companion app's ExternalAuth). */
export function findAuth(win) {
  try {
    const auth = win.document?.querySelector?.("home-assistant")?.hass?.auth;
    return auth?.accessToken ? auth : null;
  } catch (e) {
    return null;
  }
}

/**
 * Waits until Home Assistant's frontend is logged in. On the login page (or before the app has
 * started) the promise just stays pending – nothing breaks, icons appear once there is a token.
 */
export function authSource(win, { first = 100, max = 2000, sleep } = {}) {
  const wait = sleep || ((ms) => new Promise((resolve) => win.setTimeout(resolve, ms)));
  let pending = null;
  const fromConnection = async () => {
    try {
      const conn = await win.hassConnection; // set by HA's core entrypoint: Promise<{auth, conn}>
      return conn?.auth?.accessToken ? conn.auth : null;
    } catch (e) {
      return null;
    }
  };
  return () => {
    const now = findAuth(win);
    if (now) return Promise.resolve(now);
    if (!pending) {
      pending = (async () => {
        let delay = first;
        for (;;) {
          const auth = findAuth(win) || (await fromConnection());
          if (auth) return auth;
          await wait(delay);
          delay = Math.min(delay * 2, max);
        }
      })().finally(() => {
        pending = null;
      });
    }
    return pending;
  };
}

/** fetch() with the user's token; refreshes an expired token and retries once after a 401. */
export function createAuthFetch({ getAuth, fetchImpl }) {
  return async (url) => {
    for (let attempt = 0; ; attempt++) {
      const auth = await getAuth();
      if (auth.expired && auth.refreshAccessToken) await auth.refreshAccessToken();
      const res = await fetchImpl(url, {
        headers: { Authorization: `Bearer ${auth.accessToken}` },
        credentials: "same-origin",
      });
      if (res.status === 401 && attempt === 0 && auth.refreshAccessToken) {
        await auth.refreshAccessToken();
        continue;
      }
      if (!res.ok) throw new Error(`${url}: ${res.status}`);
      return res.json();
    }
  };
}

/**
 * Draws the stored layers (opacity/colour per layer) into ha-svg-icon for #hierarchical /
 * #multicolor. Returns whether the icon is layered now (the hook skips plain icons by that).
 */
export function paintLayers(el, layers) {
  const g = el.shadowRoot?.querySelector("svg > g");
  if (!g) return false;
  for (const old of g.querySelectorAll("[data-sf-layer]")) old.remove();
  const info = el.path ? layers.get(el.path) : undefined;
  for (const own of g.querySelectorAll("path")) own.style.display = info ? "none" : "";
  if (!info) return false;
  for (const layer of info) {
    const p = g.ownerDocument.createElementNS(SVG_NS, "path");
    p.setAttribute("d", layer.d);
    p.setAttribute("data-sf-layer", "");
    if (layer.fill) p.style.fill = layer.fill;
    if (layer.opacity < 1) p.style.opacity = String(layer.opacity);
    g.appendChild(p);
  }
  return true;
}

/** ha-svg-icon.updated hook: plain icons (MDI, monochrome) leave after one Map lookup. */
export function hookUpdated(updated, layers) {
  return function (changed) {
    if (updated) updated.call(this, changed);
    if (!this.__sfLayered && !(this.path && layers.has(this.path))) return;
    try {
      this.__sfLayered = paintLayers(this, layers);
    } catch (e) {
      /* never break HA's icon rendering */
    }
  };
}

function register(win) {
  const base = new URL(".", import.meta.url).href;
  const api = createSFSymbols({
    base,
    fetchJson: createAuthFetch({ getAuth: authSource(win), fetchImpl: (...args) => win.fetch(...args) }),
    warn: (msg) => win.console?.warn(msg),
  });
  const set = (prefix) => ({
    getIcon: (icon) => api.getIcon(prefix, icon),
    getIconList: () => api.getIconList(prefix),
  });
  if (!("customIcons" in win)) win.customIcons = {};
  for (const prefix of ["sf", "ios"]) {
    const value = set(prefix);
    try {
      // Takes precedence over Cupertino Icons, which also writes customIcons.ios (it would lose
      // nothing: every Cupertino name resolves here).
      Object.defineProperty(win.customIcons, prefix, {
        get: () => value,
        set: () => {},
        configurable: true,
        enumerable: true,
      });
    } catch (e) {
      win.customIcons[prefix] = value;
    }
  }
  win.sfSymbols = { version: CONFIG.version, setVersion: CONFIG.setVersion, api };
  win.customElements?.whenDefined("ha-svg-icon").then(() => {
    const proto = win.customElements.get("ha-svg-icon").prototype;
    if (proto.__sfSymbols) return;
    proto.__sfSymbols = true;
    proto.updated = hookUpdated(proto.updated, api.layers);
  });
}

if (typeof window !== "undefined" && !window.sfSymbols) register(window);
