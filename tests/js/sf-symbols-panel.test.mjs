// Symbol browser (sidebar panel): search, names, virtual grid maths, copying – against the real index.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";

import { createSFSymbols } from "../../custom_components/sf_symbols/frontend/sf-symbols.js";
import {
  buildEntries,
  copyText,
  displayName,
  gridMetrics,
  iconName,
  normalizeQuery,
  searchEntries,
  textFor,
  visibleRange,
  visibleWindow,
} from "../../custom_components/sf_symbols/frontend/sf-symbols-panel.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA = join(HERE, "../../custom_components/sf_symbols/data");
const api = createSFSymbols({
  base: "/t/",
  fetchJson: async (url) => JSON.parse(gunzipSync(readFileSync(join(DATA, `${url.slice(3)}.gz`))).toString("utf8")),
});
const entries = buildEntries(await api.getIconList("sf"));
const names = (q, allowed, n = 5) => searchEntries(entries, q, allowed).slice(0, n).map((e) => e.name);

test("panel names: sf with dots, ios with dashes, variant suffix", () => {
  assert.equal(displayName("ios", "cloud.sun.fill"), "cloud-sun-fill");
  assert.equal(displayName("sf", "cloud.sun.fill"), "cloud.sun.fill");
  assert.equal(iconName("sf", "house.fill"), "sf:house.fill");
  assert.equal(iconName("ios", "house.fill", "h"), "ios:house-fill#hierarchical");
  assert.equal(iconName("sf", "cloud.sun.fill", "m"), "sf:cloud.sun.fill#multicolor");
  assert.equal(iconName("sf", "x", "nope"), "sf:x");
});

test("panel search: query normalised like an icon name", () => {
  assert.equal(normalizeQuery("  Floor Lamp "), "floor.lamp");
  assert.equal(normalizeQuery("ios:lamp-floor#multicolor"), "lamp.floor");
  assert.equal(normalizeQuery("sf:house.fill"), "house.fill");
  assert.equal(normalizeQuery("-- a__b --"), "a.b");
  assert.equal(normalizeQuery(undefined), "");
});

test("panel search: exact names first, natural word order, German terms", () => {
  assert.equal(entries.length, 8091);
  assert.deepEqual(searchEntries(entries, ""), entries);
  assert.deepEqual(names("house", null, 2), ["house", "house.fill"]);
  assert.equal(names("sf:house.fill")[0], "house.fill");
  assert.equal(names("ios:lamp-floor")[0], "lamp.floor");
  assert.deepEqual(names("floor lamp", null, 2), ["lamp.floor", "lamp.floor.fill"]);
  assert.ok(names("stehlampe", null, 10).includes("lamp.floor"));
  assert.ok(names("glühbirne", null, 10).includes("lightbulb"));
  assert.ok(names("rollladen", null, 20).some((n) => n.startsWith("blinds.horizontal")));
  assert.deepEqual(names("gibt es nicht xyz"), []);
  // name parts rank before keyword-only hits
  const lamp = searchEntries(entries, "lamp").map((e) => e.name);
  assert.ok(lamp.indexOf("lamp.floor") < lamp.indexOf("lightbulb"));
});

test("panel search: variant filter limits the list", async () => {
  const variants = { m: new Set(["cloud.sun.fill", "house.fill"]) };
  assert.deepEqual(names("", variants.m, 10), ["cloud.sun.fill", "house.fill"]);
  assert.deepEqual(names("house", variants.m), ["house.fill"]);
});

test("panel search: fast enough for every keystroke", () => {
  const start = performance.now();
  for (const q of ["l", "la", "lam", "lamp", "lamp f", "heizung", "arrow up circle"]) searchEntries(entries, q);
  assert.ok(performance.now() - start < 300, "7 searches over 8091 symbols");
});

test("virtual grid: columns from the width, only visible rows rendered", () => {
  assert.deepEqual(gridMetrics(880, 8091, 88, 96), { cols: 10, cellWidth: 88, rows: 810, height: 77760 });
  assert.equal(gridMetrics(358, 10, 88).cols, 4); // iPhone width minus padding
  assert.equal(gridMetrics(50, 10, 88).cols, 1);
  assert.deepEqual(gridMetrics(400, 0, 88), { cols: 4, cellWidth: 100, rows: 0, height: 0 });
  // top: rows 0..(viewport/rowHeight + overscan)
  assert.deepEqual(visibleRange(0, 960, 10, 8091, 96, 3), { start: 0, end: 130 });
  // far down: overscan above and below
  assert.deepEqual(visibleRange(96 * 100, 960, 10, 8091, 96, 3), { start: 970, end: 1130 });
  // end of the list never goes past count
  assert.deepEqual(visibleRange(96 * 808, 960, 10, 8091, 96, 3), { start: 8050, end: 8091 });
  assert.deepEqual(visibleRange(0, 960, 4, 0), { start: 0, end: 0 });
  // grid not visible at all (scrolled away): only the overscan rows near the top
  assert.deepEqual(visibleRange(-5000, 0, 10, 8091, 96, 3), { start: 0, end: 30 });
});

test("virtual grid: visible window whether the scroller or the page scrolls", () => {
  // scroller below the controls (top 170), grid scrolled 960 px up inside it
  assert.deepEqual(visibleWindow({ top: -790 }, { top: 170, bottom: 860 }, 860), { top: 960, height: 690 });
  // panel taller than the window (no fixed height): the window cuts the scroller
  assert.deepEqual(visibleWindow({ top: -4000 }, { top: -4170, bottom: 70000 }, 860), { top: 4000, height: 860 });
  // scroller entirely below the window
  assert.equal(visibleWindow({ top: 900 }, { top: 900, bottom: 2000 }, 860).height, 0);
});

test("copy: clipboard API, textarea fallback over plain http, failure reported", async () => {
  const written = [];
  assert.equal(await copyText("sf:house", { clipboard: { writeText: async (t) => written.push(t) } }), true);
  assert.deepEqual(written, ["sf:house"]);

  const doc = {
    commands: [],
    body: { appendChild: (el) => (doc.appended = el) },
    createElement: () => ({
      style: {},
      setAttribute() {},
      select() {},
      setSelectionRange(a, b) {
        doc.range = [a, b];
      },
      remove() {
        doc.removed = true;
      },
    }),
    execCommand(cmd) {
      this.commands.push([cmd, this.appended.value]);
      return true;
    },
  };
  // no clipboard API (insecure context) → textarea
  assert.equal(await copyText("ios:lamp-floor", {}, doc), true);
  assert.deepEqual(doc.commands, [["copy", "ios:lamp-floor"]]);
  assert.deepEqual(doc.range, [0, 14], "explicit selection range for iOS");
  assert.equal(doc.removed, true);
  // clipboard API rejects (no permission) → textarea as well
  const denied = { clipboard: { writeText: async () => Promise.reject(new Error("denied")) } };
  assert.equal(await copyText("sf:x", denied, doc), true);
  // nothing works → false, no exception
  assert.equal(await copyText("sf:x", {}, { createElement: () => { throw new Error("no DOM"); } }), false);
});

test("panel texts: German for German users, English otherwise", () => {
  assert.equal(textFor("de").search, "Symbole suchen");
  assert.equal(textFor("de-CH").mono, "Einfarbig");
  assert.equal(textFor("fr").search, "Search symbols");
  assert.equal(textFor(undefined).copied("sf:a"), "Copied sf:a");
  assert.match(textFor("en").count(5, 8091), /^5 of 8.?091$/);
});

test("browser keeps every chunk while open: one fetch per chunk, not one per cell", async () => {
  const seen = [];
  const local = createSFSymbols({
    base: "/t/",
    fetchJson: async (url) => {
      seen.push(url);
      return JSON.parse(gunzipSync(readFileSync(join(DATA, `${url.slice(3)}.gz`))).toString("utf8"));
    },
  });
  const restore = local.widenCache();
  // one desktop screen with overscan, in index order (names spread over ~140 chunks by hash)
  await Promise.all(entries.slice(0, 180).map((e) => local.getIcon("sf", e.name)));
  for (const e of entries.slice(0, 180)) await local.getIcon("sf", e.name);
  // variant mode: outline + layer chunk per cell, the whole list once
  for (const e of entries) await local.getIcon("sf", `${e.name}#hierarchical`);
  assert.equal(seen.length, new Set(seen).size, "no chunk fetched twice");
  assert.ok(seen.filter((u) => u.includes("/v/")).length > 200);
  // a second open browser keeps the wide limit until the last one closes
  const restore2 = local.widenCache();
  restore();
  assert.ok(local.chunks.max >= 512);
  restore2();
  restore2(); // twice is harmless
  assert.equal(local.chunks.max, 48);
  assert.ok(local.chunks.size <= 48);
});
