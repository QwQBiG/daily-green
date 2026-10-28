/* Offline calendar seeds. Versioned namespaces keep existing plants reproducible. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.GreenhouseCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var PLANTS = [
    ["🌿", "薄荷"], ["☘️", "三叶草"], ["🌵", "仙人掌"],
    ["🌻", "向日葵"], ["🌱", "铃兰"], ["🍃", "含羞草"]
  ];
  var ROUND = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];

  function rotate(value, count) {
    return (value >>> count) | (value << (32 - count));
  }

  function sha256(message) {
    // Calendar seed namespaces contain ASCII only; no browser crypto or network is needed.
    var bytes = Array.from(message, function (character) { return character.charCodeAt(0); });
    var bitLength = bytes.length * 8;
    bytes.push(0x80);
    while (bytes.length % 64 !== 56) bytes.push(0);
    bytes.push(0, 0, 0, 0, (bitLength >>> 24) & 255, (bitLength >>> 16) & 255,
      (bitLength >>> 8) & 255, bitLength & 255);
    var state = new Uint32Array([
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ]);
    var words = new Uint32Array(64);
    for (var offset = 0; offset < bytes.length; offset += 64) {
      for (var i = 0; i < 16; i += 1) {
        var position = offset + i * 4;
        words[i] = ((bytes[position] << 24) | (bytes[position + 1] << 16)
          | (bytes[position + 2] << 8) | bytes[position + 3]) >>> 0;
      }
      for (var j = 16; j < 64; j += 1) {
        var small0 = rotate(words[j - 15], 7) ^ rotate(words[j - 15], 18) ^ (words[j - 15] >>> 3);
        var small1 = rotate(words[j - 2], 17) ^ rotate(words[j - 2], 19) ^ (words[j - 2] >>> 10);
        words[j] = (words[j - 16] + small0 + words[j - 7] + small1) >>> 0;
      }
      var a = state[0], b = state[1], c = state[2], d = state[3];
      var e = state[4], f = state[5], g = state[6], h = state[7];
      for (var round = 0; round < 64; round += 1) {
        var big1 = rotate(e, 6) ^ rotate(e, 11) ^ rotate(e, 25);
        var choice = (e & f) ^ (~e & g);
        var first = (h + big1 + choice + ROUND[round] + words[round]) >>> 0;
        var big0 = rotate(a, 2) ^ rotate(a, 13) ^ rotate(a, 22);
        var majority = (a & b) ^ (a & c) ^ (b & c);
        var second = (big0 + majority) >>> 0;
        h = g; g = f; f = e; e = (d + first) >>> 0;
        d = c; c = b; b = a; a = (first + second) >>> 0;
      }
      var values = [a, b, c, d, e, f, g, h];
      for (var index = 0; index < 8; index += 1) state[index] = (state[index] + values[index]) >>> 0;
    }
    var digest = new Uint8Array(32);
    for (var word = 0; word < 8; word += 1) {
      for (var byte = 0; byte < 4; byte += 1) digest[word * 4 + byte] = (state[word] >>> (24 - byte * 8)) & 255;
    }
    return digest;
  }

  function parseDate(iso) {
    if (typeof iso !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
      throw new RangeError("日期应为 YYYY-MM-DD。");
    }
    var year = Number(iso.slice(0, 4));
    var month = Number(iso.slice(5, 7));
    var day = Number(iso.slice(8, 10));
    // setUTCFullYear preserves years 0001–0099 rather than adding 1900.
    var parsed = new Date(0);
    parsed.setUTCHours(0, 0, 0, 0);
    parsed.setUTCFullYear(year, month - 1, day);
    if (year < 1 || parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1
        || parsed.getUTCDate() !== day) throw new RangeError("日期不存在。");
    return parsed;
  }

  function shiftDate(iso, deltaDays) {
    var shifted = parseDate(iso);
    if (!Number.isSafeInteger(deltaDays)) throw new RangeError("天数必须是整数。");
    shifted.setUTCDate(shifted.getUTCDate() + deltaDays);
    if (!Number.isFinite(shifted.getTime()) || shifted.getUTCFullYear() < 1
        || shifted.getUTCFullYear() > 9999) throw new RangeError("日期超出可预览范围。");
    return shifted.toISOString().slice(0, 10);
  }

  function firstEightModulo(digest, divisor) {
    // Never convert the full 64-bit seed to an imprecise JavaScript Number.
    var remainder = 0;
    for (var i = 0; i < 8; i += 1) remainder = (remainder * 256 + digest[i]) % divisor;
    return remainder;
  }

  function cardForDate(iso) {
    parseDate(iso);
    var digest = sha256("daily-green-garden-v1:" + iso);
    var speciesIndex = firstEightModulo(digest, PLANTS.length);
    var moonlight = digest[8] % 32 === 0;
    var prefix = Array.from(digest.slice(0, 3), function (byte) { return byte.toString(16).padStart(2, "0"); }).join("");
    return {
      date: iso,
      emoji: PLANTS[speciesIndex][0],
      species: PLANTS[speciesIndex][1],
      speciesIndex: speciesIndex,
      moonlight: moonlight,
      variant: moonlight ? "月光叶" : "晨绿叶",
      leaves: 2 + firstEightModulo(sha256("daily-green-v1:" + iso), 5),
      id: "DG-" + iso.replace(/-/g, "") + "-" + prefix
    };
  }

  function atmosphereForDate(iso) {
    parseDate(iso);
    // A separate seed lets the room change without changing any existing plant cards.
    var digest = sha256("daily-green-atmosphere-v1:" + iso);
    var weather = ["clear", "rain", "mist", "breeze"];
    var weatherLabels = ["晴光", "小雨", "薄雾", "微风"];
    var visitors = ["snail", "moth", "ladybird", "cat"];
    var visitorLabels = ["慢递员蜗牛", "夜航小飞蛾", "七星巡逻员", "路过的猫"];
    var notes = [
      ["今天的快递是一颗露珠，正在慢慢送来。", "蜗牛说：走得慢，也能把今天走完。", "叶子上的小路，刚刚多了一条银色脚印。"],
      ["飞蛾把一小片夜色，轻轻放在窗边。", "它不是迷路了，只是想多看一眼发亮的叶子。", "今晚的航线：从一盏小灯，到另一颗星。"],
      ["七星巡逻员检查过了，今天的叶子很安全。", "一位穿圆点外套的访客，申请在叶尖休息。", "它数了数身上的星星，决定借一颗给今天。"],
      ["猫路过窗台，留下一小块暖和的安静。", "它假装只是路过，其实已经看了很久。", "窗边的位置暂时被占领了，请轻声经过。"]
    ];
    var weatherIndex = digest[0] % weather.length;
    var visitorIndex = digest[1] % visitors.length;
    return {
      weather: weather[weatherIndex],
      weatherLabel: weatherLabels[weatherIndex],
      visitor: visitors[visitorIndex],
      visitorLabel: visitorLabels[visitorIndex],
      note: notes[visitorIndex][digest[2] % notes[visitorIndex].length]
    };
  }

  function todayInShanghai(now) {
    if (now === undefined) now = new Date();
    if (!(now instanceof Date) || !Number.isFinite(now.getTime())) throw new RangeError("当前时间无效。");
    var formatter = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Shanghai", calendar: "gregory", numberingSystem: "latn",
      year: "numeric", month: "2-digit", day: "2-digit"
    });
    var parts = {};
    formatter.formatToParts(now).forEach(function (part) { parts[part.type] = part.value; });
    var iso = parts.year.padStart(4, "0") + "-" + parts.month + "-" + parts.day;
    parseDate(iso);
    return iso;
  }

  function findMoonlightDate(fromIso, direction, limit) {
    parseDate(fromIso);
    if (direction === undefined) direction = -1;
    if (limit === undefined) limit = 120;
    if ((direction !== -1 && direction !== 1) || !Number.isSafeInteger(limit) || limit < 0 || limit > 366) {
      throw new RangeError("寻找方向应为 -1 或 1，天数应为 0–366。");
    }
    var candidate = fromIso;
    // Start with the adjacent date so repeated clicks can explore another moonlight plant.
    for (var checked = 0; checked < limit; checked += 1) {
      try { candidate = shiftDate(candidate, direction); }
      catch (error) { if (error instanceof RangeError) return null; throw error; }
      if (cardForDate(candidate).moonlight) return candidate;
    }
    return null;
  }

  return Object.freeze({
    cardForDate: cardForDate,
    atmosphereForDate: atmosphereForDate,
    parseDate: parseDate,
    shiftDate: shiftDate,
    todayInShanghai: todayInShanghai,
    findMoonlightDate: findMoonlightDate
  });
});
