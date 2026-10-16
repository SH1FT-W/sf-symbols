// SF Symbols for Home Assistant – icon sets "sf:" (Apple names, sf:lamp.floor) and
// "ios:" (Cupertino Icons compatible, ios:lamp-floor).
//
// Variants after "#": hierarchical (h) and multicolor (m), e.g. sf:cloud.sun.fill#multicolor.
// Unknown suffixes (Cupertino's #color, #invert, #fullcolor …) fall back to monochrome, which is
// what Cupertino effectively drew for them.
//
// Data: /sf_symbols/<version>/m/<xx>.json (outlines), v/<xx>.json (layers), index.json (picker list).
// The server inserts the config below; the version in the URL changes with every data/module update.

const CONFIG = /*__SF_CONFIG__*/{};
const CHUNKS = CONFIG.chunks || 256;
const FRAME = CONFIG.frame || 24;
const SVG_NS = "http://www.w3.org/2000/svg";
// Marks the path of a layered variant, so the ha-svg-icon hook can tell it apart from the
// plain outline (zero-area subpaths, invisible).
const MARK = { h: "M0 0z", m: "M0 0zM0 0z" };
const VARIANTS = { hierarchical: "h", h: "h", multicolor: "m", m: "m" };

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

export function viewBoxFor(prefix, [x, y, w, h], frame = FRAME) {
  if (prefix === "ios") return `${x} ${y} ${w} ${h}`; // tight box like Cupertino's SVGs
  const side = Math.max(w, h, frame); // shared frame: same stroke weight for all sf: symbols
  const r = (v) => Math.round(v * 100) / 100;
  return `${r(x + w / 2 - side / 2)} ${r(y + h / 2 - side / 2)} ${r(side)} ${r(side)}`;
}

/** Turns stored layers into {path, secondaryPath, layers} (secondaryPath = HA's own fallback). */
export function layered(variant, layers, mark = MARK[variant]) {
  const out = [];
  let primary = "";
  let secondary = "";
  for (const layer of layers) {
    if (variant === "h") {
      const [opacity, d] = layer;
      out.push({ d, opacity, fill: "" });
      if (opacity >= 1) primary += d;
      else secondary += d;
    } else {
      const [color, opacity, d] = layer;
      const fill = color === "#ffffff" ? "var(--sf-symbols-white, #ffffff)" : color;
      out.push({ d, opacity, fill });
      if (!color) primary += d;
      else secondary += d;
    }
  }
  return { path: primary + mark, secondaryPath: secondary || undefined, layers: out };
}

export function createSFSymbols({ base, fetchJson }) {
  const chunks = new Map();
  const layers = new Map();
  let list = null;

  const chunk = (kind, idx) => {
    const key = `${kind}/${idx}`;
    if (!chunks.has(key)) {
      const p = fetchJson(`${base}${key}.json`).catch((err) => {
        chunks.delete(key);
        throw err;
      });
      chunks.set(key, p);
    }
    return chunks.get(key);
  };

  const outline = async (name, depth = 0) => {
    const entry = (await chunk("m", chunkOf(name)))[name];
    if (typeof entry === "string" && depth < 3) return outline(entry, depth + 1); // renamed symbol
    return Array.isArray(entry) ? { name, entry } : null;
  };

  const getIcon = async (prefix, icon) => {
    const { name, variant } = parseIcon(prefix, icon);
    const found = await outline(name).catch(() => null);
    if (!found) return {};
    const [x, y, w, h, d] = found.entry;
    const viewBox = viewBoxFor(prefix, [x, y, w, h]);
    if (variant) {
      const vars = (await chunk("v", chunkOf(found.name)).catch(() => ({})))[found.name];
      if (vars?.[variant]) {
        const icn = layered(variant, vars[variant]);
        layers.set(icn.path, icn.layers);
        return { path: icn.path, secondaryPath: icn.secondaryPath, viewBox };
      }
    }
    return { path: d, viewBox };
  };

  const getIconList = async (prefix) => {
    if (!list) {
      list = fetchJson(`${base}index.json`).catch((err) => {
        list = null;
        throw err;
      });
    }
    const index = await list;
    return index.map(([name, keywords]) => ({ name: prefix === "ios" ? name.replace(/\./g, "-") : name, keywords }));
  };

  return { getIcon, getIconList, layers };
}

/** Draws the stored layers (opacity/colour per layer) into ha-svg-icon for #hierarchical / #multicolor. */
export function paintLayers(el, layers) {
  const g = el.shadowRoot?.querySelector("svg > g");
  if (!g) return;
  for (const old of g.querySelectorAll("[data-sf-layer]")) old.remove();
  const info = el.path ? layers.get(el.path) : undefined;
  for (const own of g.querySelectorAll("path")) own.style.display = info ? "none" : "";
  if (!info) return;
  for (const layer of info) {
    const p = g.ownerDocument.createElementNS(SVG_NS, "path");
    p.setAttribute("d", layer.d);
    p.setAttribute("data-sf-layer", "");
    if (layer.fill) p.style.fill = layer.fill;
    if (layer.opacity < 1) p.style.opacity = String(layer.opacity);
    g.appendChild(p);
  }
}

function register(win) {
  const base = new URL(".", import.meta.url).href;
  const api = createSFSymbols({
    base,
    fetchJson: async (url) => {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${url}: ${res.status}`);
      return res.json();
    },
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
    const updated = proto.updated;
    proto.updated = function (changed) {
      if (updated) updated.call(this, changed);
      try {
        paintLayers(this, api.layers);
      } catch (e) {
        /* never break HA's icon rendering */
      }
    };
  });
}

if (typeof window !== "undefined" && !window.sfSymbols) register(window);
