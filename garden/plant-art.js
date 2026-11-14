/* Local vector illustrations. No network, timers, randomness, or stored state. */
(function (root, factory) {
  'use strict';
  var art = factory();
  if (typeof module === 'object' && module.exports) module.exports = art;
  root.GreenhouseArt = art;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var names = ['薄荷', '三叶草', '仙人掌', '向日葵', '铃兰', '含羞草'];

  function escapeText(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character];
    });
  }

  function renderPlant(card, options) {
    card = card && typeof card === 'object' ? card : {};
    options = options && typeof options === 'object' ? options : {};
    var mini = options.mini === true;
    var kind = Number.isInteger(card.speciesIndex) && card.speciesIndex >= 0 && card.speciesIndex < 6 ? card.speciesIndex : 0;
    var leaves = Number.isInteger(card.leaves) && card.leaves >= 2 && card.leaves <= 6 ? card.leaves : 4;
    var moon = card.moonlight === true;
    var species = typeof card.species === 'string' && card.species.length < 100 ? card.species : names[kind];
    var label = escapeText(species + ' · ' + (moon ? '月光叶' : '晨绿叶'));
    var p = moon ? {
      stem: '#648a7a', dark: '#638a78', leaf: '#91b59c', light: '#d8dfaa', vein: '#f6f3d3',
      flower: '#e0d6a2', center: '#efdfab', soil: '#65543f', clay: '#c5b5ce', rim: '#e3d5e4', ink: '#527362'
    } : {
      stem: '#486b41', dark: '#3d6c48', leaf: '#6d9756', light: '#acc47b', vein: '#e5e8b2',
      flower: '#d9a249', center: '#e8c774', soil: '#5b4732', clay: '#c68b64', rim: '#e3b68b', ink: '#355e40'
    };

    function face(x, y, scale, sleepy) {
      return '<g transform="translate(' + x + ' ' + y + ') scale(' + scale + ')" fill="none" stroke="#634b3b" stroke-width="2.4" stroke-linecap="round">' +
        (sleepy ? '<path d="M-12-1q3 4 6 0m12 0q3 4 6 0"/>' : '<path d="M-9-2v3m18-3v3"/>') +
        '<path d="M-3 5q3 3 6 0" stroke-width="1.7"/><g fill="#df9e94" stroke="none" opacity=".7"><ellipse cx="-15" cy="5" rx="4" ry="2.2"/><ellipse cx="15" cy="5" rx="4" ry="2.2"/></g></g>';
    }

    function stem(d, width) {
      return '<path d="' + d + '" fill="none" stroke="' + p.stem + '" stroke-width="' + (width || 3) + '" stroke-linecap="round" stroke-linejoin="round"/>';
    }

    function leaf(x, y, scale, angle, fill, mirrored) {
      return '<g transform="translate(' + x + ' ' + y + ') rotate(' + angle + ') scale(' + (mirrored ? -scale : scale) + ' ' + scale + ')">' +
        '<path d="M0 0C-8-19-26-23-37-12C-36 3-17 10 0 0Z" fill="' + fill + '" stroke="' + p.ink + '" stroke-width=".9"/>' +
        '<path d="M-2-2C-13-17-25-20-34-12C-24-14-12-5-2-2Z" fill="' + p.light + '" opacity=".46"/>' +
        '<path d="M-1 0C-12 6-27 5-34-5C-21 0-11-1-1 0Z" fill="#1d4936" opacity=".2"/>' +
        '<path d="M-3-1Q-18-9-32-11" fill="none" stroke="' + p.vein + '" stroke-opacity=".58" stroke-width=".85" stroke-linecap="round"/>' +
        (mini ? '' : '<path d="M-15-6L-19-15M-23-9L-30-4" fill="none" stroke="' + p.vein + '" stroke-opacity=".28" stroke-width=".65" stroke-linecap="round"/>') + '</g>';
    }

    function sparkle(x, y, size) {
      return '<path d="M' + x + ' ' + (y - size) + 'Q' + x + ' ' + y + ' ' + (x + size) + ' ' + y + 'Q' + x + ' ' + y + ' ' + x + ' ' + (y + size) + 'Q' + x + ' ' + y + ' ' + (x - size) + ' ' + y + 'Q' + x + ' ' + y + ' ' + x + ' ' + (y - size) + 'Z" fill="#d6b56b"/>';
    }

    function mint() {
      return stem('M150 229C144 190 156 147 151 95') +
        leaf(149, 204, 1.08, -8, p.dark) + leaf(150, 186, 1.05, 4, p.leaf, true) +
        leaf(151, 167, .96, 3, p.leaf) + leaf(152, 147, .96, -8, p.light, true) +
        leaf(152, 128, .75, 12, p.light) + leaf(151, 108, .63, -15, p.leaf, true) +
        leaf(151, 97, .49, 52, p.light);
    }

    function cloverHead(x, y, scale, fill) {
      var petals = '';
      for (var i = 0; i < 3; i++) {
        petals += '<g transform="rotate(' + (i * 120) + ')"><path d="M0 2C-19-1-27-20-15-27C-7-32-1-26 0-21C4-31 14-30 20-23C30-10 16 1 0 2Z" fill="' + fill + '" stroke="' + p.ink + '" stroke-width="1.5"/>' +
          (mini ? '' : '<path d="M0-2 0-19" stroke="' + p.vein + '" stroke-width="1" stroke-opacity=".42"/>') + '</g>';
      }
      return '<g transform="translate(' + x + ' ' + y + ') scale(' + scale + ')">' + petals + '</g>';
    }

    function clover() {
      return stem('M149 229Q144 190 110 151M150 229Q159 166 160 111M151 229Q178 189 200 159', 2.7) +
        cloverHead(110, 151, .83, p.dark) + cloverHead(160, 111, 1.0, p.light) + cloverHead(200, 159, .8, p.leaf);
    }

    function cactus() {
      var art = '<path d="M134 191H108Q78 191 78 161V145Q78 132 91 132Q104 132 104 145V159Q104 169 115 169H134Z" fill="' + p.dark + '" stroke="' + p.ink + '" stroke-width="1.8"/>' +
        '<path d="M170 164H187Q217 164 217 134V119Q217 106 204 106Q191 106 191 119V132Q191 141 180 141H170Z" fill="' + p.leaf + '" stroke="' + p.ink + '" stroke-width="1.8"/>' +
        '<rect x="127" y="80" width="47" height="151" rx="23.5" fill="' + p.leaf + '" stroke="' + p.ink + '" stroke-width="1.2"/>' +
        '<path d="M153 81Q175 83 174 108V224H162Q166 148 153 81Z" fill="#2e5942" opacity=".28"/>' +
        '<path d="M143 89Q132 107 136 181" fill="none" stroke="' + p.light + '" stroke-width="7" stroke-opacity=".53" stroke-linecap="round"/>' +
        '<path d="M143 91Q138 142 140 218M158 91Q165 146 160 220" fill="none" stroke="' + p.light + '" stroke-width="1.5" stroke-opacity=".62"/>';
      if (!mini) {
        for (var y = 112; y < 216; y += 22) {
          art += '<path d="M128 ' + y + 'l-4-3m5 6-5 2M173 ' + (y + 5) + 'l5-2m-5 5 4 3" fill="none" stroke="' + p.vein + '" stroke-width="1" stroke-linecap="round"/>';
        }
        art += '<path d="M86 147h9m-4-4v8M199 120h9m-4-4v8" stroke="' + p.vein + '" stroke-width="1" stroke-opacity=".7"/>';
      }
      return art + face(151, 136, .7, false) + '<g transform="translate(151 81)"><ellipse cy="-7" rx="5" ry="8" fill="' + (moon ? '#ddd5eb' : '#e8acb6') + '"/><ellipse cx="-6" cy="-2" rx="7" ry="4" fill="' + (moon ? '#eee6f2' : '#f3c7cc') + '"/><ellipse cx="6" cy="-2" rx="7" ry="4" fill="' + (moon ? '#eee6f2' : '#f3c7cc') + '"/><circle r="3" fill="' + p.center + '"/></g>';
    }

    function sunflower() {
      var petals = '';
      for (var i = 0; i < 12; i++) {
        petals += '<ellipse cx="150" cy="69" rx="9.5" ry="20" fill="' + (i % 2 ? p.flower : (moon ? '#e5e4bb' : '#e4c579')) + '" transform="rotate(' + (i * 30) + ' 150 100)"/>';
      }
      return stem('M151 229C153 188 145 145 150 102', 4) +
        leaf(150, 190, 1.37, -12, p.dark) + leaf(150, 165, 1.24, -2, p.leaf, true) + petals +
        '<circle cx="150" cy="100" r="24" fill="' + p.center + '" stroke="#b89049" stroke-width="1.2"/><path d="M130 91a22 22 0 0 1 30-11" fill="none" stroke="#f8e5ac" stroke-width="4" stroke-linecap="round"/><path d="M169 88a22 22 0 0 1-5 29" fill="none" stroke="#b48c48" stroke-width="3" stroke-linecap="round" opacity=".28"/>' + face(150, 99, .8, false);
    }

    function bell(x, y, scale) {
      return '<g transform="translate(' + x + ' ' + y + ') scale(' + scale + ')"><path d="M-10 1C-11-11-5-18 0-18C6-18 11-10 10 1Q6-1 3 3Q0 0-3 3Q-6-1-10 1Z" fill="' + (moon ? '#f2eaf7' : '#fff4de') + '"/>' +
        '<path d="M-3-12Q-5-7-5-3" fill="none" stroke="#fff9df" stroke-opacity=".65" stroke-width="1.2" stroke-linecap="round"/><circle cy="4" r="1.6" fill="' + p.center + '"/></g>';
    }

    function lily() {
      return '<path d="M151 230C94 211 93 152 126 114C142 151 157 193 151 230Z" fill="' + p.dark + '"/>' +
        '<path d="M150 230C190 215 214 166 195 122C170 152 151 194 150 230Z" fill="' + p.leaf + '"/>' +
        (mini ? '' : '<path d="M149 225Q119 175 126 126M153 225Q184 175 193 135" fill="none" stroke="' + p.vein + '" stroke-width="1.1" stroke-opacity=".4"/>') +
        stem('M151 229C144 179 145 107 174 100C193 96 209 113 207 138', 2.8) +
        stem('M170 102Q164 108 168 123M184 102Q182 112 185 128M198 111Q195 122 199 139M206 126Q204 135 208 151', 1.8) +
        bell(168, 138, .85) + bell(185, 143, .9) + bell(199, 154, .84) + bell(208, 167, .74);
    }

    function frond(x1, y1, x2, y2, fill) {
      var dx = x2 - x1, dy = y2 - y1;
      var length = Math.sqrt(dx * dx + dy * dy);
      var angle = Math.atan2(dy, dx) * 180 / Math.PI;
      var art = stem('M' + x1 + ' ' + y1 + 'L' + x2 + ' ' + y2, 1.8);
      for (var i = 0; i < 5; i++) {
        var t = .22 + i * .16;
        var x = x1 + dx * t, y = y1 + dy * t;
        var size = Math.max(5.7, length * .135 * (1 - i * .07));
        art += '<g transform="translate(' + x.toFixed(2) + ' ' + y.toFixed(2) + ') rotate(' + angle.toFixed(2) + ')"><ellipse cy="' + (-size * .65).toFixed(2) + '" rx="3.8" ry="' + size.toFixed(2) + '" fill="' + fill + '" transform="rotate(-24)"/><ellipse cy="' + (size * .65).toFixed(2) + '" rx="3.8" ry="' + size.toFixed(2) + '" fill="' + fill + '" transform="rotate(24)"/></g>';
      }
      return art;
    }

    function mimosa() {
      var art = stem('M149 230Q145 180 158 118', 2.5) +
        frond(150, 195, 91, 163, p.dark) + frond(151, 182, 209, 157, p.leaf) +
        frond(154, 160, 112, 126, p.leaf) + frond(157, 145, 200, 114, p.light) +
        frond(158, 126, 151, 89, p.light);
      var puffColor = moon ? '#ccc3df' : '#deaab8';
      for (var n = 0; n < 2; n++) {
        var cx = 130 + n * 42, cy = 112 - n * 16;
        art += stem('M157 145Q' + cx + ' 124 ' + cx + ' ' + cy, 1.2);
        for (var i = 0; i < (mini ? 8 : 16); i++) {
          var angle = i * Math.PI * 2 / (mini ? 8 : 16);
          art += '<path d="M' + cx + ' ' + cy + 'l' + (Math.cos(angle) * 10).toFixed(2) + ' ' + (Math.sin(angle) * 10).toFixed(2) + '" stroke="' + puffColor + '" stroke-width="1" stroke-linecap="round"/>';
        }
        art += '<circle cx="' + cx + '" cy="' + cy + '" r="4" fill="' + puffColor + '"/>';
      }
      return art;
    }

    var foliage = [mint, clover, cactus, sunflower, lily, mimosa][kind]();
    var growth = .82 + (leaves - 2) * .045;
    var pot = '<g class="plant-pot"><ellipse cx="150" cy="291" rx="67" ry="11" fill="#203c2b" opacity=".1"/><ellipse cx="150" cy="288" rx="53" ry="5" fill="#283c2a" opacity=".15"/>' +
      '<ellipse cx="150" cy="282" rx="58" ry="11" fill="' + (moon ? '#9b8aa8' : '#a76b49') + '"/>' +
      '<ellipse cx="150" cy="279" rx="58" ry="9" fill="' + (moon ? '#c8b9cc' : '#d2a078') + '"/>' +
      '<ellipse cx="150" cy="278" rx="45" ry="5" fill="' + (moon ? '#89798f' : '#956342') + '" opacity=".43"/>' +
      '<path d="M103 231H197L188 271Q186 283 173 285H127Q114 283 112 271Z" fill="' + p.clay + '" stroke="' + (moon ? '#938099' : '#9b6446') + '" stroke-width="1.2" stroke-linejoin="round"/>' +
      '<path d="M108 238H191L183 269Q180 279 168 280H131Q120 279 118 268Z" fill="' + (moon ? '#ddcfdf' : '#dba67e') + '" opacity=".75"/>' +
      '<path d="M179 237H195L187 271Q184 282 171 284H165Q177 271 179 237Z" fill="' + (moon ? '#7e6c8b' : '#885135') + '" opacity=".25"/>' +
      '<path d="M114 240 121 266Q123 273 130 275" fill="none" stroke="' + (moon ? '#f5eaf5' : '#ffe8bd') + '" stroke-width="6" stroke-linecap="round" opacity=".56"/>' +
      '<path d="M128 278Q151 284 174 277" fill="none" stroke="' + (moon ? '#b3a2bc' : '#bd7f57') + '" stroke-width="1.6" opacity=".7"/>' +
      (mini ? '' : '<g fill="#fff0c9" opacity=".23"><circle cx="136" cy="242" r=".8"/><circle cx="165" cy="248" r=".7"/><circle cx="176" cy="256" r=".9"/><circle cx="132" cy="267" r=".9"/><circle cx="160" cy="272" r=".7"/></g>') +
      '<ellipse cx="150" cy="231" rx="52" ry="13" fill="' + p.rim + '" stroke="' + (moon ? '#a18ca7' : '#b37a52') + '" stroke-width="1.2"/>' +
      '<path d="M101 231Q150 213 199 231" fill="none" stroke="' + (moon ? '#f4e8f2' : '#fae0b8') + '" stroke-width="2.2" stroke-linecap="round"/>' +
      '<ellipse cx="150" cy="229" rx="44" ry="8" fill="' + p.soil + '"/>' +
      '<path d="M108 230Q150 214 192 230Q154 220 108 230Z" fill="#30291d" opacity=".38"/>' +
      '<g fill="#a0875b" opacity=".6"><circle cx="124" cy="229" r="1.2"/><circle cx="171" cy="228" r="1.1"/><circle cx="140" cy="225" r=".8"/><circle cx="160" cy="233" r="1"/></g>' +
      face(150, 256, .72, kind === 4 || moon) +
      '<path d="M101 233Q150 249 199 233" fill="none" stroke="' + p.rim + '" stroke-width="4" stroke-linecap="round"/></g>';

    return '<svg xmlns="http://www.w3.org/2000/svg" class="plant-art" viewBox="0 0 300 320" width="300" height="320" role="img" aria-label="' + label + '" data-species="' + kind + '">' +
      '<title>' + label + '</title><desc>装饰性的盆栽插画；植物长势由这一天固定的日历种子决定。</desc>' +
      (moon ? '<ellipse cx="150" cy="159" rx="92" ry="105" fill="#d8d0e9" opacity=".18"/>' : '') +
      pot + '<g class="plant-sway" style="transform-origin:150px 228px"><g transform="translate(150 228) scale(' + growth.toFixed(3) + ') translate(-150 -228)">' + foliage + '</g></g>' +
      (moon ? '<g class="plant-sparkles" aria-hidden="true">' + sparkle(76, 108, 5) + sparkle(225, 173, 4) + sparkle(209, 74, 3) + '</g>' : '') + '</svg>';
  }

  return Object.freeze({ renderPlant: renderPlant });
});
