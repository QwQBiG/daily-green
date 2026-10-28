"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const core = require("../garden/garden-core.js");

// Frozen calendar-card fixtures preserve plant identities across versions.
const fixtures = [
  ["2025-11-15", "☘️", "三叶草", 1, false, 5, "DG-20251115-ef699e"],
  ["2025-11-16", "🍃", "含羞草", 5, false, 3, "DG-20251116-9dab4c"],
  ["2025-11-17", "🌱", "铃兰", 4, false, 5, "DG-20251117-4e9e6a"],
  ["2025-11-18", "🌿", "薄荷", 0, false, 2, "DG-20251118-6748ca"],
  ["2025-11-21", "🌻", "向日葵", 3, false, 6, "DG-20251121-ef34cb"],
  ["2025-12-02", "🌵", "仙人掌", 2, false, 3, "DG-20251202-64993a"],
  ["2025-12-06", "☘️", "三叶草", 1, true, 6, "DG-20251206-b2529f"],
  ["2026-10-26", "🌿", "薄荷", 0, false, 5, "DG-20261026-8b8345"],
  ["0001-01-01", "🌻", "向日葵", 3, false, 6, "DG-00010101-981bab"],
  ["2024-02-29", "🌱", "铃兰", 4, false, 3, "DG-20240229-6a4ca7"],
  ["9999-12-31", "🌿", "薄荷", 0, false, 6, "DG-99991231-dc55ac"]
];
for (const [date, emoji, species, speciesIndex, moonlight, leaves, id] of fixtures) {
  assert.deepEqual(core.cardForDate(date), {
    date, emoji, species, speciesIndex, moonlight,
    variant: moonlight ? "月光叶" : "晨绿叶", leaves, id
  });
}

// Node's independent SHA-256 and 64-bit BigInt arithmetic detect precision/rounding mistakes.
for (let index = 0; index < 500; index += 1) {
  const date = core.shiftDate("2025-11-15", index);
  const garden = crypto.createHash("sha256").update("daily-green-garden-v1:" + date).digest();
  const planned = crypto.createHash("sha256").update("daily-green-v1:" + date).digest();
  const card = core.cardForDate(date);
  assert.equal(card.speciesIndex, Number(garden.readBigUInt64BE() % 6n));
  assert.equal(card.moonlight, garden[8] % 32 === 0);
  assert.equal(card.leaves, 2 + Number(planned.readBigUInt64BE() % 5n));
  assert.equal(card.id, "DG-" + date.replace(/-/g, "") + "-" + garden.toString("hex").slice(0, 6));
  assert.deepEqual(card, core.cardForDate(date));
}

// Room surprises have their own seed and never change plant identity.
const weatherNames = ["clear", "rain", "mist", "breeze"];
const visitorNames = ["snail", "moth", "ladybird", "cat"];
const seenWeather = new Set(), seenVisitors = new Set(), seenNotes = new Set();
for (let index = 0; index < 500; index += 1) {
  const date = core.shiftDate("2025-11-15", index);
  const seed = crypto.createHash("sha256").update("daily-green-atmosphere-v1:" + date).digest();
  const atmosphere = core.atmosphereForDate(date);
  assert.deepEqual(Object.keys(atmosphere).sort(), ["note", "visitor", "visitorLabel", "weather", "weatherLabel"]);
  assert.equal(atmosphere.weather, weatherNames[seed[0] % 4]);
  assert.equal(atmosphere.visitor, visitorNames[seed[1] % 4]);
  assert.equal(atmosphere.weatherLabel, ["晴光", "小雨", "薄雾", "微风"][seed[0] % 4]);
  assert.equal(atmosphere.visitorLabel, ["慢递员蜗牛", "夜航小飞蛾", "七星巡逻员", "路过的猫"][seed[1] % 4]);
  assert.equal(typeof atmosphere.note, "string");
  assert.ok(atmosphere.note.length > 5);
  assert.deepEqual(atmosphere, core.atmosphereForDate(date));
  // Returned state is independent, so callers cannot alter a later visit to the same date.
  atmosphere.note = "caller mutation";
  assert.notEqual(core.atmosphereForDate(date).note, atmosphere.note);
  seenWeather.add(atmosphere.weather); seenVisitors.add(atmosphere.visitor);
  seenNotes.add(core.atmosphereForDate(date).note);
}
assert.deepEqual([...seenWeather].sort(), [...weatherNames].sort());
assert.deepEqual([...seenVisitors].sort(), [...visitorNames].sort());
assert.equal(seenNotes.size, 12);
for (const date of ["0001-01-01", "0099-12-31", "2000-02-29", "2024-02-29", "9999-12-31"]) {
  const seed = crypto.createHash("sha256").update("daily-green-atmosphere-v1:" + date).digest();
  assert.equal(core.atmosphereForDate(date).weather, weatherNames[seed[0] % 4]);
  assert.equal(core.atmosphereForDate(date).visitor, visitorNames[seed[1] % 4]);
}

for (const value of [null, undefined, 20261026, "", "2026-1-01", "2026-01-1", "0000-01-01",
  "2026-02-29", "1900-02-29", "2026-04-31", "2026-00-10", "2026-13-01", "2026-01-00",
  "2026-10-26T00:00:00Z", "2026-10-26 ", "10000-01-01", "private-value"]) {
  assert.throws(() => core.parseDate(value), RangeError);
  assert.throws(() => core.cardForDate(value), RangeError);
  assert.throws(() => core.atmosphereForDate(value), RangeError);
}
assert.equal(core.parseDate("0001-01-01").toISOString(), "0001-01-01T00:00:00.000Z");
assert.equal(core.parseDate("0099-12-31").getUTCFullYear(), 99);
assert.equal(core.parseDate("2000-02-29").getUTCDate(), 29);
assert.equal(core.shiftDate("2024-02-28", 1), "2024-02-29");
assert.equal(core.shiftDate("2024-02-29", 1), "2024-03-01");
assert.equal(core.shiftDate("2026-03-01", -1), "2026-02-28");
assert.equal(core.shiftDate("2026-12-31", 1), "2027-01-01");
assert.equal(core.shiftDate("0001-01-02", -1), "0001-01-01");
assert.throws(() => core.shiftDate("0001-01-01", -1), RangeError);
assert.throws(() => core.shiftDate("9999-12-31", 1), RangeError);
for (const offset of [NaN, Infinity, 1.5, "1", Number.MAX_SAFE_INTEGER]) {
  assert.throws(() => core.shiftDate("2026-10-26", offset), RangeError);
}

assert.equal(core.todayInShanghai(new Date("2026-10-25T15:59:59Z")), "2026-10-25");
assert.equal(core.todayInShanghai(new Date("2026-10-25T16:00:00Z")), "2026-10-26");
assert.equal(core.todayInShanghai(new Date("2026-12-31T18:00:00Z")), "2027-01-01");
assert.throws(() => core.todayInShanghai(new Date(NaN)), RangeError);
assert.throws(() => core.todayInShanghai("2026-10-26"), RangeError);

assert.equal(core.findMoonlightDate("2025-12-07", -1, 1), "2025-12-06");
assert.equal(core.findMoonlightDate("2025-12-05", 1, 1), "2025-12-06");
assert.equal(core.findMoonlightDate("2025-12-06", -1, 0), null);
assert.equal(core.findMoonlightDate("0001-01-01", -1, 120), null);
assert.equal(core.findMoonlightDate("9999-12-31", 1, 120), null);
const previousMoonlight = core.findMoonlightDate("2026-10-26");
assert.ok(previousMoonlight < "2026-10-26");
assert.equal(core.cardForDate(previousMoonlight).moonlight, true);
assert.equal(previousMoonlight, core.findMoonlightDate("2026-10-26"));
for (const args of [["2026-10-26", 0, 120], ["2026-10-26", -1, -1],
  ["2026-10-26", 1, 367], ["2026-10-26", -1, 0.5]]) {
  assert.throws(() => core.findMoonlightDate(...args), RangeError);
}

// The same file also works as a plain browser script, without require/WebCrypto/fetch.
const browser = vm.createContext({ Date, Intl, Uint32Array, Uint8Array });
vm.runInContext(fs.readFileSync(path.join(__dirname, "../garden/garden-core.js"), "utf8"), browser);
assert.equal(browser.GreenhouseCore.cardForDate("2026-10-26").id, "DG-20261026-8b8345");
assert.equal(browser.GreenhouseCore.findMoonlightDate("2025-12-07", -1, 1), "2025-12-06");
assert.equal(JSON.stringify(browser.GreenhouseCore.atmosphereForDate("2026-10-28")), JSON.stringify(core.atmosphereForDate("2026-10-28")));

console.log("Garden core passed: frozen fixtures, 500 plant and atmosphere crypto parity dates, 4 weather/4 visitor/12 note coverage, calendar/timezone boundaries, bounded moonlight search, offline browser export.");
