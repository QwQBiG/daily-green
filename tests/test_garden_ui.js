"use strict";

// Controller integration only: a deliberately small DOM model, not a browser,
// layout engine, visual check, or substitute for accessibility/browser testing.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const Core = require("../garden/garden-core.js");
const garden = path.join(__dirname, "../garden");
const STORE = "daily-green-greenhouse-v1";
const GUEST_STORE = "daily-green-visitors-v1";
const FIXED_NOW = Date.parse("2026-10-26T04:00:00Z");
const html = fs.readFileSync(path.join(garden, "index.html"), "utf8");
const scripts = Array.from(html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi));
const controller = scripts.at(-1)[1];

// The downloadable page must remain self-contained and match the tested libraries.
assert.equal(/<script\b[^>]*\bsrc\s*=/i.test(html), false);
for (const name of ["garden-core.js", "plant-art.js", "visitor-art.js"]) {
  const embedded = html.match(new RegExp('<script data-source="' + name.replace(/\./g, '\\.') + '">([\\s\\S]*?)<\\/script>'));
  assert.ok(embedded, "Expected embedded " + name);
  assert.equal(embedded[1].trim(), fs.readFileSync(path.join(garden, name), "utf8").trim());
}

class Element {
  constructor(tagName, document) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = document;
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.dataset = {};
    this.handlers = new Map();
    this._className = "";
    this._text = "";
    this._html = "";
    this.connected = false;
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.offsetWidth = 0; // Reading this models a reflow trigger, not actual layout.
    this.classList = {
      contains: name => this.className.split(/\s+/).includes(name),
      add: (...names) => { this.className = [...new Set([...this.className.split(/\s+/), ...names].filter(Boolean))].join(" "); },
      remove: (...names) => { this.className = this.className.split(/\s+/).filter(name => name && !names.includes(name)).join(" "); },
      toggle: (name, force) => {
        const selected = force === undefined ? !this.classList.contains(name) : Boolean(force);
        selected ? this.classList.add(name) : this.classList.remove(name);
        return selected;
      }
    };
  }
  get className() { return this._className; }
  set className(value) { this._className = String(value); this.attributes.set("class", this._className); }
  get textContent() { return this._text + this.children.map(node => node.textContent).join(""); }
  set textContent(value) { this.replaceChildren(); this._text = String(value); this._html = ""; }
  get innerHTML() { return this._html; }
  set innerHTML(value) { this.replaceChildren(); this._html = String(value); this._text = this._html.replace(/<[^>]*>/g, ""); }
  setConnected(connected) { this.connected = connected; this.children.forEach(node => node.setConnected(connected)); }
  append(...nodes) {
    for (let node of nodes) {
      if (typeof node === "string") { const text = this.ownerDocument.createElement("span"); text.textContent = node; node = text; }
      if (node.parentNode) node.parentNode.children = node.parentNode.children.filter(child => child !== node);
      node.parentNode = this; node.setConnected(this.connected); this.children.push(node);
    }
  }
  replaceChildren(...nodes) {
    for (const node of this.children) { node.parentNode = null; node.setConnected(false); }
    this.children = []; this._text = ""; this._html = ""; this.append(...nodes);
  }
  setAttribute(name, value) {
    value = String(value); this.attributes.set(name, value);
    if (name === "class") this._className = value;
    if (name.startsWith("data-")) this.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = value;
  }
  getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
  removeAttribute(name) {
    this.attributes.delete(name);
    if (name.startsWith("data-")) delete this.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())];
  }
  addEventListener(type, handler) { if (!this.handlers.has(type)) this.handlers.set(type, []); this.handlers.get(type).push(handler); }
  dispatch(type) {
    const event = { type, target: this, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
    for (const handler of this.handlers.get(type) || []) handler(event);
    return event;
  }
  click() { if (!this.disabled) return this.dispatch("click"); }
  focus() { this.ownerDocument.activeElement = this; }
}

function makeDocument() {
  const document = {
    elements: new Map(), all: [], activeElement: null,
    createElement(tag) { const node = new Element(tag, this); this.all.push(node); return node; },
    getElementById(id) { return this.elements.get(id) || null; },
    querySelector(selector) { assert.equal(selector, ".brand"); return this.brand; },
    querySelectorAll(selector) { assert.equal(selector, "button"); return this.all.filter(node => node.tagName === "BUTTON" && node.connected); }
  };
  // IDs and initial attributes come from the real page, so renamed/missing IDs fail.
  for (const match of html.matchAll(/<([a-z][\w:-]*)\b([^>]*\bid=["']([^"']+)["'][^>]*)>/gi)) {
    const [, tag, attributes, id] = match;
    assert.ok(!document.elements.has(id), "duplicate page ID: " + id);
    const node = document.createElement(tag); node.id = id; node.connected = true;
    for (const attr of attributes.matchAll(/([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g)) node.setAttribute(attr[1], attr[2] === undefined ? attr[3] : attr[2]);
    const closing = html.indexOf("</" + tag + ">", match.index + match[0].length);
    if (closing >= 0) node._text = html.slice(match.index + match[0].length, closing).replace(/<[^>]*>/g, "");
    document.elements.set(id, node);
  }
  assert.match(html, /<a\b[^>]*class="brand"/);
  document.brand = document.createElement("a"); document.brand.className = "brand"; document.brand.connected = true;
  return document;
}

const boots = [];
function boot(options = {}) {
  const document = makeDocument();
  const data = options.data || new Map();
  const timers = new Map(); let timerId = 0, writes = 0, requests = 0;
  class FixedDate extends Date { constructor(...args) { super(...(args.length ? args : [FIXED_NOW])); } static now() { return FIXED_NOW; } }
  const math = Object.create(Math); math.random = () => 0.37;
  const networkTrap = function () { requests += 1; throw new Error("Unexpected network access"); };
  const sandbox = {
    document, Date: FixedDate, Intl, Math: math, URLSearchParams,
    location: { search: options.search || "" },
    setTimeout(fn, delay) { const id = ++timerId; timers.set(id, { fn, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    fetch: networkTrap, XMLHttpRequest: networkTrap, WebSocket: networkTrap,
    navigator: { sendBeacon: networkTrap }
  };
  Object.defineProperty(sandbox, "localStorage", { get() {
    if (options.unavailable) throw new Error("Storage denied");
    return {
      getItem(key) { return data.has(key) ? data.get(key) : null; },
      setItem(key, value) { if (options.quota) throw new Error("Storage quota exceeded"); writes += 1; data.set(key, String(value)); }
    };
  } });
  const context = vm.createContext(sandbox);
  if (!options.missingCore) vm.runInContext(fs.readFileSync(path.join(garden, "garden-core.js"), "utf8"), context, { filename: "garden-core.js" });
  if (!options.missingArt) vm.runInContext(fs.readFileSync(path.join(garden, "plant-art.js"), "utf8"), context, { filename: "plant-art.js" });
  if (!options.missingVisitors) vm.runInContext(fs.readFileSync(path.join(garden, "visitor-art.js"), "utf8"), context, { filename: "visitor-art.js" });
  vm.runInContext(controller, context, { filename: "garden-controller.js", timeout: 1000 });
  const harness = {
    document, data, timers,
    get writes() { return writes; }, get requests() { return requests; },
    el(id) { const node = document.getElementById(id); assert.ok(node, "missing page ID: " + id); return node; },
    click(id) { return this.el(id).click(); },
    select(day) { this.el("plant-date").value = day; this.el("plant-date").dispatch("change"); },
    flushTimers() { const pending = [...timers.values()]; timers.clear(); pending.forEach(timer => timer.fn()); }
  };
  boots.push(harness); return harness;
}

let scenarios = 0;
function test(name, run) { run(); scenarios += 1; console.log("ok - " + name); }
function shown(harness, day) {
  const card = Core.cardForDate(day);
  assert.equal(harness.el("plant-date").value, day);
  assert.equal(harness.el("plant-name").textContent, card.species);
  assert.equal(harness.el("seed-id").textContent, card.id);
  assert.equal(harness.el("leaf-value").textContent, `${card.leaves} / 6`);
  assert.equal(harness.el("leaf-meter").getAttribute("aria-valuenow"), String(card.leaves));
  assert.equal(harness.el("leaf-meter").children.length, 6);
  assert.equal(harness.el("leaf-meter").children.filter(node => node.classList.contains("filled")).length, card.leaves);
  assert.match(harness.el("plant-display").innerHTML, /<svg\b/);
  assert.equal(harness.el("scene").classList.contains("moonlight"), card.moonlight);
  return card;
}

test("initial fixed Shanghai date shows mint, five leaves, and its exact seed", () => {
  const page = boot(); shown(page, "2026-10-26");
  assert.equal(page.el("saved-count").textContent, "0");
  assert.equal(page.el("album-progress").textContent, "认识了 0 / 6 种植物");
  assert.equal(page.el("album").children.length, 6); assert.equal(page.writes, 0);
});

test("date controls, neighbors, today, brand and deterministic wandering change visible state", () => {
  const page = boot(); page.select("2025-12-06"); shown(page, "2025-12-06");
  page.click("previous-day"); shown(page, "2025-12-05");
  page.click("next-day"); shown(page, "2025-12-06");
  page.click("neighbor-right"); shown(page, "2025-12-07");
  page.click("neighbor-left"); shown(page, "2025-12-06");
  page.click("today-button"); shown(page, "2026-10-26");
  page.select("2024-02-29"); page.document.brand.click(); shown(page, "2026-10-26");
  page.click("wander-button");
  const day = page.el("plant-date").value; assert.ok(day >= "2025-11-15" && day <= "2026-10-26"); shown(page, day);
});

test("watering toggles only the bounded animation lifecycle, never the seed or leaves", () => {
  const page = boot(); const seed = page.el("seed-id").textContent;
  page.click("water-button"); assert.ok(page.el("scene").classList.contains("watered"));
  assert.equal(page.timers.size, 1); assert.equal([...page.timers.values()][0].delay, 1300);
  page.click("water-button"); assert.equal(page.timers.size, 1); shown(page, "2026-10-26");
  page.flushTimers(); assert.ok(!page.el("scene").classList.contains("watered"));
  assert.equal(page.el("seed-id").textContent, seed); assert.equal(page.writes, 0);
  page.click("water-button"); page.select("2025-12-06"); assert.equal(page.timers.size, 0);
  assert.ok(!page.el("scene").classList.contains("watered"));
});

test("saving survives a new controller instance and toggling removes the date", () => {
  const page = boot(); page.click("save-button");
  assert.equal(page.el("saved-count").textContent, "1");
  assert.equal(page.el("save-button").getAttribute("aria-pressed"), "true");
  assert.equal(JSON.parse(page.data.get(STORE)).dates[0], "2026-10-26");
  const reopened = boot({ data: page.data }); shown(reopened, "2026-10-26");
  assert.equal(reopened.el("saved-count").textContent, "1");
  reopened.click("save-button"); assert.equal(reopened.el("saved-count").textContent, "0");
  assert.equal(reopened.el("save-button").getAttribute("aria-pressed"), "false");
  assert.deepEqual(JSON.parse(reopened.data.get(STORE)).dates, []);
});

test("collecting six species updates the album and album/chip controls select saved plants", () => {
  const page = boot();
  for (const day of ["2025-11-15", "2025-11-16", "2025-11-17", "2025-11-18", "2025-11-21", "2025-12-02"]) {
    page.select(day); page.click("save-button");
  }
  assert.equal(page.el("album-progress").textContent, "认识了 6 / 6 种植物");
  assert.equal(page.el("saved-count").textContent, "6");
  assert.ok(page.el("album").children.every(node => node.tagName === "BUTTON" && node.classList.contains("unlocked")));
  page.el("album").children[0].click(); shown(page, "2025-11-18");
  assert.equal(page.document.activeElement, page.el("plant-date"));
  page.el("saved-dates").children.find(node => node.textContent === "2025-11-15").click(); shown(page, "2025-11-15");
});

test("moonlight discovery updates the room, card, saved album mark and seed consistently", () => {
  const page = boot(); page.click("moon-button");
  const day = page.el("plant-date").value; assert.equal(shown(page, day).moonlight, true);
  assert.match(page.el("variant-text").textContent, /月光叶/);
  assert.equal(page.el("room-label").textContent, "月光温室");
  page.click("save-button");
  assert.ok(page.el("album").children.some(node => node.children.some(child => child.classList.contains("album-moon"))));
});

test("invalid input resets the field, preserves the plant and clears its error after a valid choice", () => {
  const page = boot();
  for (const invalid of ["", "2026-02-30", "private-value"]) {
    page.select(invalid); shown(page, "2026-10-26"); assert.ok(page.el("notice").classList.contains("error"));
    assert.ok(!page.el("notice").textContent.includes("private-value"));
  }
  page.select("2025-12-06"); shown(page, "2025-12-06"); assert.ok(!page.el("notice").classList.contains("error"));
});

test("calendar boundaries disable navigation and neighbor previews without changing the chosen date", () => {
  const page = boot(); page.select("0001-01-01"); shown(page, "0001-01-01");
  assert.ok(page.el("previous-day").disabled && page.el("neighbor-left").disabled);
  assert.equal(page.el("neighbor-left").dataset.date, undefined);
  assert.equal(page.el("neighbor-left-art").children.length, 0);
  page.click("previous-day"); shown(page, "0001-01-01");
  page.select("9999-12-31"); shown(page, "9999-12-31");
  assert.ok(page.el("next-day").disabled && page.el("neighbor-right").disabled);
  page.click("next-day"); shown(page, "9999-12-31");
  page.click("today-button"); assert.ok(!page.el("previous-day").disabled && !page.el("next-day").disabled);
});

test("saved data is filtered, deduplicated, capped and full collections can remove then add", () => {
  const dates = Array.from({ length: 50 }, (_, index) => Core.shiftDate("2025-11-15", index));
  const data = new Map([[STORE, JSON.stringify({ version: 1, dates: [null, 4, "bad", dates[0], ...dates] })]]);
  const page = boot({ data }); assert.equal(page.el("saved-count").textContent, "48");
  page.select("2030-01-01"); const before = page.writes; page.click("save-button");
  assert.equal(page.writes, before); assert.match(page.el("notice").textContent, /48/);
  page.select(dates[0]); page.click("save-button"); assert.equal(page.el("saved-count").textContent, "47");
  page.select("2030-01-01"); page.click("save-button"); assert.equal(page.el("saved-count").textContent, "48");
});

test("malformed, unavailable and quota-limited storage keep the local session playable", () => {
  const malformed = boot({ data: new Map([[STORE, "{broken"]]) }); shown(malformed, "2026-10-26");
  assert.match(malformed.el("storage-note").textContent, /本次页面/); malformed.click("save-button");
  assert.equal(malformed.el("saved-count").textContent, "1");
  for (const options of [{ unavailable: true }, { quota: true }]) {
    const page = boot(options); page.click("save-button");
    assert.equal(page.el("saved-count").textContent, "1"); assert.match(page.el("storage-note").textContent, /本次页面/);
    assert.equal(page.writes, 0); shown(page, "2026-10-26");
    assert.equal(boot(options).el("saved-count").textContent, "0");
  }
});

test("URL dates preview valid seeds and safely discard invalid requests", () => {
  shown(boot({ search: "?date=2025-12-06" }), "2025-12-06");
  shown(boot({ search: "?date=%3Cscript%3Eprivate-value%3C%2Fscript%3E" }), "2026-10-26");
  assert.equal(boot({ data: new Map([[STORE, JSON.stringify({ version: 2, dates: ["2025-12-06"] })]]) }).el("saved-count").textContent, "0");
});

test("missing core or artwork produces a safe error state, including the brand link", () => {
  for (const options of [{ missingCore: true }, { missingArt: true }, { missingVisitors: true }]) {
    const page = boot(options);
    assert.match(page.el("plant-display").innerHTML, /温室暂时没有打开/);
    assert.ok(page.el("notice").classList.contains("error"));
    assert.ok(page.document.querySelectorAll("button").every(button => button.disabled));
    assert.ok(page.el("plant-date").disabled);
    assert.equal(page.document.brand.getAttribute("aria-disabled"), "true");
    assert.doesNotThrow(() => page.document.brand.click());
    assert.equal(page.writes, 0);
  }
});

test("date weather and visitors are fixed, while night is a reversible session choice", () => {
  const page = boot(); const seed = page.el("seed-id").textContent;
  const atmosphere = Core.atmosphereForDate("2026-10-26");
  assert.equal(page.el("scene").dataset.weather, atmosphere.weather);
  assert.equal(page.el("weather-label").textContent, atmosphere.weatherLabel);
  assert.equal(page.el("visitor-button").dataset.kind, atmosphere.visitor);
  assert.match(page.el("visitor-art").innerHTML, /data-visitor="cat"/);
  page.click("night-button");
  assert.equal(page.el("night-button").getAttribute("aria-pressed"), "true");
  assert.ok(page.el("scene").classList.contains("night-room"));
  assert.equal(page.el("room-label").textContent, "晚灯温室");
  page.select("2025-12-06"); assert.ok(page.el("scene").classList.contains("night-room"));
  page.click("night-button"); assert.equal(page.el("room-label").textContent, "月光温室");
  page.select("2026-10-26"); assert.equal(page.el("seed-id").textContent, seed);
  assert.equal(page.el("scene").dataset.weather, atmosphere.weather);
  assert.equal(page.writes, 0); assert.equal(page.timers.size, 0);
});

test("greeting collects four unique visitor stamps without altering plant storage", () => {
  const data = new Map([[STORE, JSON.stringify({version:1,dates:["2025-12-06"]})]]);
  const page = boot({data}); const plantData = data.get(STORE);
  const firstDates = new Map();
  for(let offset=0;offset<30;offset++) {
    const day = Core.shiftDate("2026-10-01", offset);
    const kind = Core.atmosphereForDate(day).visitor;
    if(!firstDates.has(kind)) firstDates.set(kind,day);
  }
  assert.equal(firstDates.size,4);
  for(const day of firstDates.values()) {
    page.select(day); const before = page.writes; page.click("visitor-button");
    assert.equal(page.writes,before+1); assert.match(page.el("visitor-note").textContent,/^「.+」$/);
    assert.ok(page.el("visitor-note").classList.contains("revealed"));
    assert.ok(page.el("visitor-button").classList.contains("greeted"));
    page.click("visitor-button"); assert.equal(page.writes,before+1);
  }
  assert.match(page.el("guest-progress").textContent,/相遇 4 \/ 4/);
  assert.equal(JSON.parse(data.get(GUEST_STORE)).dates.length,4);
  assert.equal(data.get(STORE),plantData);
  const reopened=boot({data});assert.match(reopened.el("guest-progress").textContent,/相遇 4 \/ 4/);
  const savedDay=JSON.parse(data.get(GUEST_STORE)).dates[0];
  const firstKind=Core.atmosphereForDate(savedDay).visitor;
  const slot=["snail","moth","ladybird","cat"].indexOf(firstKind);
  reopened.el("guest-stamps").children[slot].click();shown(reopened,savedDay);
  assert.equal(reopened.document.activeElement,reopened.el("visitor-button"));
  assert.ok(reopened.el("visitor-note").classList.contains("revealed"));assert.equal(reopened.writes,0);
});

test("visitor storage validates dates and unique kinds and stays playable when saving is denied", () => {
  const dates=Array.from({length:30},(_,i)=>Core.shiftDate("2026-10-01",i));
  const data=new Map([[GUEST_STORE,JSON.stringify({version:1,dates:[null,"bad",7,"2026-02-30",...dates,...dates]})]]);
  const page=boot({data});assert.match(page.el("guest-progress").textContent,/相遇 4 \/ 4/);assert.equal(page.writes,0);
  const malformed=boot({data:new Map([[GUEST_STORE,"{bad"]])});shown(malformed,"2026-10-26");
  malformed.click("visitor-button");assert.match(malformed.el("guest-progress").textContent,/相遇 1 \/ 4/);
  for(const options of [{unavailable:true},{quota:true}]) {
    const denied=boot(options);denied.click("visitor-button");
    assert.match(denied.el("guest-progress").textContent,/相遇 1 \/ 4/);
    assert.match(denied.el("storage-note").textContent,/本次页面/);assert.equal(denied.writes,0);
    denied.select("2025-12-06");shown(denied,"2025-12-06");
  }
});

assert.ok(boots.every(page => page.requests === 0), "a controller operation attempted network access");
console.log(`Garden controller: ${scenarios} DOM-model integration scenarios passed; zero network calls. Browser layout/visual behavior was not tested.`);
