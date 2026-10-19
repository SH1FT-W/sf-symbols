// Frontend-Modul gegen die echten Daten: node --test tests/js
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";

import {
  authSource,
  canonical,
  chunkOf,
  createAuthFetch,
  createSFSymbols,
  findAuth,
  fitFor,
  fnv1a,
  hookUpdated,
  layered,
  Lru,
  MAX_CHUNKS,
  paintLayers,
  parseIcon,
  scalePath,
  viewBoxFor,
} from "../../custom_components/sf_symbols/frontend/sf-symbols.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA = join(HERE, "../../custom_components/sf_symbols/data");
const fetched = [];
const warnings = [];
const api = createSFSymbols({
  base: "/sf_symbols/test/",
  warn: (msg) => warnings.push(msg),
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

test("viewBox: ios eng wie Cupertino, sf immer dasselbe Quadrat", () => {
  assert.equal(viewBoxFor("ios", [1, 2, 10, 20], 24), "1 2 10 20");
  assert.equal(viewBoxFor("sf", [1, 2, 10, 20], 24), "-6 0 24 24");
  // zu breit: gleiches Quadrat, die Form wird um die Mitte verkleinert
  const wide = fitFor("sf", [0, 0, 30, 10], 24);
  assert.equal(wide.viewBox, "3 -7 24 24");
  assert.equal(wide.scale, 0.8);
  assert.equal(fitFor("sf", [1, 2, 10, 20], 24).scale, 1);
});

test("scalePath: absolutes M um die Mitte, Rest relativ, kompakte Zahlen", () => {
  assert.equal(scalePath("M1 2h3", 1), "M1 2h3");
  assert.equal(scalePath("M10 10h10v-5c1.5.5-2 0 1 1zM2 2z", 0.5, 1, 2), "M6 7h5v-2.5c0.75 0.25-1 0 0.5 0.5zM2 3z");
});

test("ios: und sf: liefern dieselbe Form, sf: alle im selben Quadrat", async () => {
  const a = await api.getIcon("ios", "lightbulb");
  const b = await api.getIcon("sf", "lightbulb");
  assert.ok(a.path.startsWith("M"));
  assert.equal(a.path, b.path);
  assert.notEqual(a.viewBox, b.viewBox);
  const sides = new Set();
  for (const n of ["lamp.floor", "house", "lightbulb", "heater.vertical", "tv", "textformat.characters.si", "circle"]) {
    const icon = await api.getIcon("sf", n);
    assert.ok(icon.path, n);
    sides.add(icon.viewBox.split(" ").slice(2).join(" "));
  }
  assert.deepEqual([...sides], ["24 24"]);
  // tv (24,41 breit) passt nicht ganz ins 24er-Quadrat → verkleinert, ios: bleibt unverändert
  const tv = await api.getIcon("sf", "tv");
  assert.notEqual(tv.path, (await api.getIcon("ios", "tv")).path);
  assert.ok(tv.path.startsWith("M") && !tv.path.includes("  "));
});

test("unbekannte Symbole: leeres Ergebnis, eine Warnung je Name", async () => {
  warnings.length = 0;
  assert.deepEqual(await api.getIcon("sf", "gibt.es.nicht"), {});
  assert.deepEqual(await api.getIcon("sf", "gibt.es.nicht"), {});
  assert.deepEqual(await api.getIcon("sf", "gibt.es.nicht#multicolor"), {});
  assert.deepEqual(await api.getIcon("ios", "auch-nicht"), {});
  assert.deepEqual(warnings, ["SF Symbols: unknown icon sf:gibt.es.nicht", "SF Symbols: unknown icon ios:auch-nicht"]);
});

test("Daten nicht erreichbar (kein Login): leeres Ergebnis, kein Absturz, später neuer Versuch", async () => {
  let fail = true;
  const calls = [];
  const seen = [];
  const local = createSFSymbols({
    base: "/x/",
    fetchJson: async (url) => {
      calls.push(url);
      if (fail) throw new Error(`${url}: 401`);
      return { house: [0, 0, 20, 20, "M0 0h1z"] };
    },
    warn: (msg) => seen.push(msg),
  });
  assert.deepEqual(await local.getIcon("sf", "house"), {});
  assert.deepEqual(await local.getIcon("sf", "house"), {});
  // eine Warnung, nicht eine je Symbol
  assert.deepEqual(seen, ["SF Symbols: icon data not reachable (/x/m/" + chunkOf("house") + ".json: 401)"]);
  await assert.rejects(local.getIconList("sf"));
  fail = false;
  assert.equal((await local.getIcon("sf", "house")).path, "M0 0h1z");
  assert.equal(calls.length, 4);
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

test("layered: Weiß = Textfarbe über CSS-Variable, Hauptfarbe = currentColor", () => {
  const r = layered("m", [["", 1, "M1 1z"], ["#ffffff", 1, "M2 2z"]], "");
  assert.equal(r.path, "M1 1z");
  assert.equal(r.secondaryPath, "M2 2z");
  assert.equal(r.layers[1].fill, "var(--sf-symbols-white, var(--primary-text-color))");
});

test("Picker-Liste: ios mit Bindestrich, Suchbegriffe inkl. Deutsch", async () => {
  const ios = await api.getIconList("ios");
  const sf = await api.getIconList("sf");
  assert.ok(ios.length > 7000);
  assert.equal(ios.length, sf.length);
  const names = new Set(ios.map((i) => i.name));
  assert.ok(names.has("lamp-floor") && names.has("lamp-floor-fill") && names.has("cloud-sun-fill"));
  // Casoras Prüfung: zu jedem genutzten Namen die -fill-Variante finden
  assert.ok(names.has("house-fill") && names.has("lightbulb-fill"));
  assert.ok(ios.every((i) => !i.keywords), "Suchbegriffe nur an sf:");
  assert.ok(sf.some((i) => i.name === "lamp.floor"));
  const bulb = sf.find((i) => i.name === "lightbulb");
  assert.ok(bulb.keywords.includes("glühbirne"));
  assert.ok(sf.every((i) => i.keywords.every((k) => !/\s/.test(k))), "keine Leerzeichen in Suchbegriffen");
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

// HAs Suche im Symbol-Picker (ha-icon-picker._filterIcons, HA 2026.10), 1:1 nachgebaut, mit HAs Aufbereitung
// der Einträge (search_labels = Name, Namensteile an "-", Suchbegriffe).
function haSearch(items, query) {
  const s = query.toLowerCase().replace(/\s+/g, "-");
  const out = [];
  for (const item of items) {
    const parts = (item.id.split(":")[1] || item.id).toLowerCase().split("-");
    const labels = Object.values(item.search_labels).map((v) => v.toLowerCase());
    const id = item.id.toLowerCase();
    if (parts.includes(s)) out.push({ item, rank: 1 });
    else if (labels.includes(s)) out.push({ item, rank: 2 });
    else if (id.includes(s)) out.push({ item, rank: 3 });
    else if (labels.some((l) => l.includes(s))) out.push({ item, rank: 4 });
  }
  return out.sort((a, b) => a.rank - b.rank).map((r) => r.item.id);
}

async function pickerItems() {
  const items = [];
  for (const prefix of ["sf", "ios"]) {
    for (const icon of await api.getIconList(prefix)) {
      const labels = { iconName: icon.name };
      icon.name.split("-").forEach((p, i) => (labels[`part${i}`] = p));
      (icon.keywords ?? []).forEach((k, i) => (labels[`keyword${i}`] = k));
      items.push({ id: `${prefix}:${icon.name}`, search_labels: labels });
    }
  }
  return items;
}

test("Picker-Suche: Smart-Home-Wörter, natürliche Reihenfolge, keine Fehltreffer", async () => {
  const items = await pickerItems();
  const top = (q, n = 10) => haSearch(items, q).slice(0, n);
  assert.ok(top("rollladen").some((id) => id.startsWith("sf:blinds.horizontal")), top("rollladen").join());
  assert.ok(top("rollladen").some((id) => id.startsWith("sf:roller.shade")));
  const heizung = haSearch(items, "heizung");
  assert.ok(heizung.slice(0, 4).some((id) => id.startsWith("sf:heater.vertical")), heizung.slice(0, 4).join());
  assert.ok(!heizung.some((id) => /carseat|cup\.and|steeringwheel/.test(id)), "heat → Heizung zu breit");
  assert.deepEqual(top("floor lamp", 2), ["sf:lamp.floor", "sf:lamp.floor.fill"]);
  assert.ok(top("stehlampe").includes("sf:lamp.floor"));
  assert.ok(!haSearch(items, "fernseher").includes("sf:gear"));
  assert.ok(haSearch(items, "fernseher").includes("sf:tv"));
  assert.ok(!haSearch(items, "müll").includes("sf:eject"));
  assert.ok(haSearch(items, "müll").includes("sf:trash"));
  // deutsche Wörter: jeder Treffer nur einmal (sf:), keine ios:-Doppel
  for (const q of ["rollladen", "steckdose", "waschmaschine", "saugroboter", "präsenz", "leck", "markise", "gewitter"]) {
    const hits = haSearch(items, q);
    assert.ok(hits.length > 0, q);
    assert.ok(hits.every((id) => id.startsWith("sf:")), q);
  }
  // Englisch einwortig: sf: steht dank Namensteilen als Suchbegriff vor den Teil-Treffern
  assert.ok(haSearch(items, "lamp").includes("sf:lamp.floor"));
});

test("Lru: Größe begrenzt, zuletzt gelesen bleibt", () => {
  const lru = new Lru(2);
  lru.set("a", 1).set("b", 2);
  assert.equal(lru.get("a"), 1);
  lru.set("c", 3);
  assert.deepEqual([...lru.keys()], ["a", "c"]);
  lru.set("a", 4);
  assert.deepEqual([...lru.keys()], ["c", "a"]);
  assert.equal(lru.get("zz"), undefined);
});

test("Speicher: Stücke und Ebenen begrenzt", async () => {
  const local = createSFSymbols({ base: "/x/", fetchJson: async () => ({}) });
  for (let i = 0; i < 300; i++) await local.getIcon("sf", `name${i}`);
  assert.ok(MAX_CHUNKS < 256);
  assert.ok(local.layers.max > 0);
});

test("Anmeldung: Token aus <home-assistant>.hass.auth oder window.hassConnection", async () => {
  const auth = { accessToken: "t1", expired: false };
  const doc = { el: null, querySelector: (sel) => (sel === "home-assistant" ? doc.el : null) };
  const win = { document: doc };
  assert.equal(findAuth(win), null);
  assert.equal(findAuth({ document: { querySelector: () => { throw new Error("x"); } } }), null);
  doc.el = { hass: { auth } };
  assert.equal(findAuth(win), auth);
  assert.equal(await authSource(win)(), auth);

  // Login-Seite: wartet, bis es ein Token gibt; mehrere Anfragen teilen sich das Warten
  const slept = [];
  const later = { document: { querySelector: () => null }, hassConnection: undefined };
  let turn = 0;
  const get = authSource(later, {
    first: 10,
    max: 40,
    sleep: async (ms) => {
      slept.push(ms);
      if (++turn === 4) later.hassConnection = Promise.resolve({ auth });
    },
  });
  const [x, y] = await Promise.all([get(), get()]);
  assert.equal(x, auth);
  assert.equal(y, auth);
  assert.deepEqual(slept, [10, 20, 40, 40]);
  // abgelehnte hassConnection bricht nichts
  const broken = { document: { querySelector: () => null }, hassConnection: Promise.reject(new Error("no")) };
  broken.hassConnection.catch(() => {});
  let n = 0;
  const get2 = authSource(broken, {
    sleep: async () => {
      if (++n === 2) broken.document.querySelector = () => ({ hass: { auth } });
    },
  });
  assert.equal(await get2(), auth);
});

test("Abruf mit Token: abgelaufen → erneuern, 401 → einmal erneuern und wiederholen", async () => {
  const auth = {
    accessToken: "alt",
    expired: true,
    refreshes: 0,
    async refreshAccessToken() {
      this.refreshes++;
      this.accessToken = `neu${this.refreshes}`;
      this.expired = false;
    },
  };
  const seen = [];
  let status = [200];
  const fetchImpl = async (url, init) => {
    seen.push(init.headers.Authorization);
    const s = status.shift();
    return { ok: s === 200, status: s, json: async () => ({ url }) };
  };
  const get = createAuthFetch({ getAuth: async () => auth, fetchImpl });
  assert.deepEqual(await get("/a"), { url: "/a" });
  assert.deepEqual(seen, ["Bearer neu1"]);
  status = [401, 200];
  assert.deepEqual(await get("/b"), { url: "/b" });
  assert.deepEqual(seen.slice(1), ["Bearer neu1", "Bearer neu2"]);
  status = [401, 401];
  await assert.rejects(get("/c"), /401/);
  status = [404];
  await assert.rejects(get("/d"), /404/);
  // ohne Erneuern-Funktion (z. B. fremdes Auth-Objekt): 401 sofort als Fehler
  const plain = createAuthFetch({ getAuth: async () => ({ accessToken: "x" }), fetchImpl });
  status = [401];
  await assert.rejects(plain("/e"), /401/);
});

test("ha-svg-icon-Hook: Symbole ohne Ebenen steigen ohne DOM-Zugriff aus", () => {
  let base = 0;
  const layers = new Map([["L", [{ d: "M1 1z", opacity: 1, fill: "" }]]]);
  const hook = hookUpdated(function () {
    base++;
  }, layers);
  const untouchable = {
    path: "mdi-path",
    get shadowRoot() {
      throw new Error("DOM touched");
    },
  };
  hook.call(untouchable, new Map());
  hook.call({ path: undefined }, new Map());
  assert.equal(base, 2);
  // mit Ebenen: zeichnen, danach wieder einfarbig → einmal aufräumen
  const g = {
    kids: [],
    ownerDocument: { createElementNS: () => ({ style: {}, setAttribute() {}, remove() {} }) },
    appendChild(n) {
      this.kids.push(n);
    },
    querySelectorAll: () => [],
  };
  const el = { path: "L", shadowRoot: { querySelector: () => g } };
  hook.call(el, new Map());
  assert.equal(el.__sfLayered, true);
  el.path = "plain";
  hook.call(el, new Map());
  assert.equal(el.__sfLayered, false);
  // Fehler im Zeichnen bricht HAs Darstellung nicht
  const bad = { path: "L", get shadowRoot() { throw new Error("boom"); } };
  hookUpdated(undefined, layers).call(bad, new Map());
  assert.equal(paintLayers({ path: "L" }, layers), false);
});
