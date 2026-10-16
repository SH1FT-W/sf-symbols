// Frontend-Modul gegen die echten Daten: node --test tests/js
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";

import {
  canonical,
  chunkOf,
  createSFSymbols,
  fnv1a,
  layered,
  paintLayers,
  parseIcon,
  viewBoxFor,
} from "../../custom_components/sf_symbols/frontend/sf-symbols.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA = join(HERE, "../../custom_components/sf_symbols/data");
const fetched = [];
const api = createSFSymbols({
  base: "/sf_symbols/test/",
  fetchJson: async (url) => {
    fetched.push(url);
    const rel = url.replace("/sf_symbols/test/", "");
    return JSON.parse(gunzipSync(readFileSync(join(DATA, `${rel}.gz`))).toString("utf8"));
  },
});

test("Hash wie im Python-Generator", () => {
  assert.equal(fnv1a(""), 0x811c9dc5);
  assert.equal(fnv1a("a"), 0xe40c292c);
  assert.match(chunkOf("lamp.floor"), /^[0-9a-f]{2}$/);
});

test("Namen und Varianten", () => {
  assert.equal(canonical("ios", "lamp-floor"), "lamp.floor");
  assert.equal(canonical("sf", "lamp.floor"), "lamp.floor");
  assert.deepEqual(parseIcon("ios", "cloud-sun-fill#multicolor"), { name: "cloud.sun.fill", variant: "m" });
  assert.deepEqual(parseIcon("sf", "wifi#H"), { name: "wifi", variant: "h" });
  assert.deepEqual(parseIcon("ios", "house#color-invert"), { name: "house", variant: "" });
});

test("viewBox: ios eng wie Cupertino, sf im gemeinsamen Rahmen", () => {
  assert.equal(viewBoxFor("ios", [1, 2, 10, 20], 24), "1 2 10 20");
  assert.equal(viewBoxFor("sf", [1, 2, 10, 20], 24), "-6 0 24 24");
  assert.equal(viewBoxFor("sf", [0, 0, 30, 10], 24), "0 -10 30 30");
});

test("ios: und sf: liefern dieselbe Form", async () => {
  const a = await api.getIcon("ios", "lamp-floor");
  const b = await api.getIcon("sf", "lamp.floor");
  assert.ok(a.path.startsWith("M"));
  assert.equal(a.path, b.path);
  assert.notEqual(a.viewBox, b.viewBox);
});

test("unbekannte Symbole: leeres Ergebnis statt Fehler", async () => {
  assert.deepEqual(await api.getIcon("sf", "gibt.es.nicht"), {});
});

test("umbenannte Symbole lösen über Aliase auf", async () => {
  const icon = await api.getIcon("ios", "arrow-upright-circle");
  assert.ok(icon.path, "legacy alias arrow.upright.circle → arrow.up.right.circle");
});

test("hierarchisch und mehrfarbig", async () => {
  const h = await api.getIcon("sf", "cloud.sun.fill#hierarchical");
  assert.ok(h.path.endsWith("M0 0z") && h.secondaryPath);
  const layers = api.layers.get(h.path);
  assert.ok(layers.some((l) => l.opacity < 1));
  const m = await api.getIcon("ios", "cloud-sun-fill#multicolor");
  assert.ok(api.layers.get(m.path).some((l) => l.fill === "#ffcc00"));
  // ohne Ebenen-Daten bleibt es einfarbig
  const plain = await api.getIcon("sf", "lamp.floor#multicolor");
  assert.equal(plain.path, (await api.getIcon("sf", "lamp.floor")).path);
});

test("layered: Weiß über CSS-Variable, Hauptfarbe = currentColor", () => {
  const r = layered("m", [["", 1, "M1 1z"], ["#ffffff", 1, "M2 2z"]], "");
  assert.equal(r.path, "M1 1z");
  assert.equal(r.secondaryPath, "M2 2z");
  assert.equal(r.layers[1].fill, "var(--sf-symbols-white, #ffffff)");
});

test("Picker-Liste: ios mit Bindestrich, Suchbegriffe inkl. Deutsch", async () => {
  const ios = await api.getIconList("ios");
  const sf = await api.getIconList("sf");
  assert.ok(ios.length > 7000);
  const names = new Set(ios.map((i) => i.name));
  assert.ok(names.has("lamp-floor") && names.has("lamp-floor-fill"));
  assert.ok(sf.some((i) => i.name === "lamp.floor"));
  const bulb = sf.find((i) => i.name === "lightbulb");
  assert.ok(bulb.keywords.includes("Glühbirne"));
  assert.equal(fetched.filter((u) => u.endsWith("index.json")).length, 1, "index only loaded once");
});

test("alle im Haus genutzten ios:-Namen lösen auf", async () => {
  const used = JSON.parse(readFileSync(join(HERE, "../data/used_ios_names.json"), "utf8"));
  const all = [...used.prod_entities, ...used.prod_dashboards, ...used.casora];
  const missing = [];
  for (const icon of all) {
    const r = await api.getIcon("ios", icon.slice(4));
    if (!r.path) missing.push(icon);
  }
  assert.deepEqual(missing, []);
});

test("alle 6945 Cupertino-Namen lösen auf", async () => {
  const names = readFileSync(join(HERE, "../data/cupertino_names.txt"), "utf8").split("\n").filter(Boolean);
  assert.equal(names.length, 6945);
  const missing = [];
  for (const n of names) if (!(await api.getIcon("ios", n)).path) missing.push(n);
  assert.deepEqual(missing, []);
});

test("paintLayers: zeichnet Ebenen und räumt wieder auf", () => {
  const made = [];
  const mk = (tag) => {
    const node = {
      tag,
      style: {},
      attrs: {},
      setAttribute(k, v) {
        this.attrs[k] = v;
      },
      remove() {
        g.children.splice(g.children.indexOf(this), 1);
      },
    };
    made.push(node);
    return node;
  };
  const own = mk("path");
  const g = {
    children: [own],
    ownerDocument: { createElementNS: (_ns, tag) => mk(tag) },
    appendChild(n) {
      this.children.push(n);
    },
    querySelectorAll(sel) {
      return sel === "path" ? this.children.filter((c) => !("data-sf-layer" in c.attrs)) : this.children.filter((c) => "data-sf-layer" in c.attrs);
    },
  };
  const el = { path: "P", shadowRoot: { querySelector: () => g } };
  const layers = new Map([["P", [{ d: "M1 1z", opacity: 0.5, fill: "" }, { d: "M2 2z", opacity: 1, fill: "red" }]]]);
  paintLayers(el, layers);
  assert.equal(own.style.display, "none");
  assert.equal(g.children.length, 3);
  assert.equal(g.children[1].style.opacity, "0.5");
  assert.equal(g.children[2].style.fill, "red");
  el.path = "other";
  paintLayers(el, layers);
  assert.equal(own.style.display, "");
  assert.equal(g.children.length, 1);
});
