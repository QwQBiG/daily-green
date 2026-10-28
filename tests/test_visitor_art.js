'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const visitors = require('../garden/visitor-art.js');

const kinds = ['snail', 'moth', 'ladybird', 'cat'];
const drawings = kinds.map(kind => visitors.renderVisitor(kind));
assert.equal(new Set(drawings).size, 4, 'Each visitor has its own illustration.');
for (let index = 0; index < kinds.length; index += 1) {
  const drawing = drawings[index];
  assert.match(drawing, /^<svg\s/);
  assert.match(drawing, /<\/svg>$/);
  assert.match(drawing, /viewBox="0 0 100 80"/);
  assert.match(drawing, new RegExp('data-visitor="' + kinds[index] + '"'));
  assert.match(drawing, /role="img" aria-label="[^"]+"/);
  assert.match(drawing, /<title>[^<]+<\/title>/);
  assert.ok(Buffer.byteLength(drawing) < 3000, 'Each inline illustration stays small.');
  assert.doesNotMatch(drawing, /<(?:script|image|foreignObject|iframe|style)\b|\bon\w+=|\b(?:href|id)=|url\(/i);
  assert.equal(drawing, visitors.renderVisitor(kinds[index]), 'Illustration has no random or clock state.');
}
for (const value of [undefined, null, '', 'bee', '__proto__', 'constructor', '<script>', {}, 1]) {
  assert.throws(() => visitors.renderVisitor(value), RangeError);
}
assert.ok(Object.isFrozen(visitors));

const browser = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../garden/visitor-art.js'), 'utf8'), browser);
assert.equal(browser.GreenhouseVisitors.renderVisitor('cat'), drawings[3]);
console.log('Visitor art passed: four distinct small accessible SVG drawings, invalid kinds rejected, offline browser export.');
