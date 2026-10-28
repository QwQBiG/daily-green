/* Tiny greenhouse visitors, drawn entirely with local SVG paths. */
(function (root, factory) {
  'use strict';
  var art = factory();
  if (typeof module === 'object' && module.exports) module.exports = art;
  root.GreenhouseVisitors = art;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var visitors = {
    snail: {
      name: '慢慢走的小蜗牛',
      art: '<ellipse cx="48" cy="69" rx="36" ry="4" fill="#07180e" opacity=".18"/>' +
        '<path d="M13 62Q20 56 43 56H65Q69 55 71 46Q72 39 78 41Q85 44 81 55L78 61Q88 62 89 66Q74 72 20 68Q9 68 13 62Z" fill="#aabd82"/>' +
        '<path d="M23 65Q40 62 60 65" fill="none" stroke="#d7ddb0" stroke-width="1.5" stroke-linecap="round"/>' +
        '<circle cx="43" cy="46" r="23" fill="#bd916a"/>' +
        '<path d="M44 63C18 65 20 27 44 29C65 30 62 56 44 56C30 56 30 37 44 38C53 39 53 50 44 49" fill="none" stroke="#795f46" stroke-width="2" stroke-linecap="round"/>' +
        '<path d="M73 45 70 33M79 44 84 32" fill="none" stroke="#aabd82" stroke-width="2.5" stroke-linecap="round"/>' +
        '<circle cx="70" cy="32" r="2.5" fill="#dbe0b7"/><circle cx="84" cy="31" r="2.5" fill="#dbe0b7"/>' +
        '<circle cx="70.5" cy="32" r="1.1" fill="#263e2b"/><circle cx="84.5" cy="31" r="1.1" fill="#263e2b"/>' +
        '<path d="M75 52q2 2 4 0" fill="none" stroke="#61794e" stroke-width="1.2" stroke-linecap="round"/>'
    },
    moth: {
      name: '借月光的小飞蛾',
      art: '<path d="M47 40C35 13 13 14 15 34C16 47 30 51 46 48Z" fill="#d8d6a7"/>' +
        '<path d="M53 40C65 13 87 14 85 34C84 47 70 51 54 48Z" fill="#e8e3bb"/>' +
        '<path d="M46 45C22 44 23 68 36 67Q46 66 49 49Z" fill="#afb98a"/>' +
        '<path d="M54 45C78 44 77 68 64 67Q54 66 51 49Z" fill="#c6cd9d"/>' +
        '<path d="M22 30Q35 31 43 42M78 30Q65 31 57 42M31 57l12-8M69 57l-12-8" fill="none" stroke="#85976e" stroke-width="1.2" stroke-opacity=".65" stroke-linecap="round"/>' +
        '<ellipse cx="29" cy="35" rx="4" ry="5" fill="#9ba781"/><ellipse cx="71" cy="35" rx="4" ry="5" fill="#acb18c"/>' +
        '<ellipse cx="50" cy="45" rx="4" ry="16" fill="#a09670"/><circle cx="50" cy="29" r="5" fill="#d5c99a"/>' +
        '<path d="M48 25q-1-9-7-10M52 25q1-9 7-10" fill="none" stroke="#c7c79c" stroke-width="1.5" stroke-linecap="round"/>' +
        '<circle cx="48" cy="29" r=".9" fill="#354733"/><circle cx="52" cy="29" r=".9" fill="#354733"/>'
    },
    ladybird: {
      name: '停在叶边的小瓢虫',
      art: '<ellipse cx="50" cy="66" rx="24" ry="4" fill="#07180e" opacity=".18"/>' +
        '<path d="M32 38 23 33m9 15-11 1m16 8-10 8M68 38l9-5M68 48l11 1M63 57l10 8" fill="none" stroke="#758266" stroke-width="2.2" stroke-linecap="round"/>' +
        '<ellipse cx="50" cy="44" rx="23" ry="24" fill="#b9795e"/>' +
        '<path d="M50 24v43" fill="none" stroke="#684e3c" stroke-width="2"/>' +
        '<path d="M31 35Q33 25 43 24" fill="none" stroke="#e2b18a" stroke-width="2.2" stroke-linecap="round" opacity=".65"/>' +
        '<g fill="#5e5940"><circle cx="38" cy="37" r="4"/><circle cx="63" cy="37" r="4"/><circle cx="37" cy="52" r="3.4"/><circle cx="63" cy="52" r="3.4"/><circle cx="44" cy="61" r="2.6"/><circle cx="56" cy="61" r="2.6"/></g>' +
        '<path d="M42 24q-5-7-8-7M58 24q5-7 8-7" fill="none" stroke="#8e9d76" stroke-width="1.8" stroke-linecap="round"/>' +
        '<ellipse cx="50" cy="25" rx="12" ry="10" fill="#697859"/>' +
        '<circle cx="45" cy="23" r="2.5" fill="#e5e3bc"/><circle cx="55" cy="23" r="2.5" fill="#e5e3bc"/>' +
        '<circle cx="45" cy="23.5" r="1.2" fill="#273d2a"/><circle cx="55" cy="23.5" r="1.2" fill="#273d2a"/>'
    },
    cat: {
      name: '来窗边打盹的小猫',
      art: '<ellipse cx="50" cy="70" rx="35" ry="4" fill="#07180e" opacity=".18"/>' +
        '<path d="M72 64Q96 66 89 44Q85 36 80 43Q79 47 84 50Q90 61 72 58" fill="#c6ae85"/>' +
        '<path d="M29 68Q20 51 33 42Q47 33 65 44Q79 51 74 67Z" fill="#d4bd93"/>' +
        '<path d="M33 41 27 19Q37 19 43 26M55 26Q63 18 70 19L66 42" fill="#d4bd93"/>' +
        '<path d="m31 24 3 12 7-6M65 24l-3 12-6-6" fill="#b98d79"/>' +
        '<path d="M29 35Q32 25 48 26Q66 24 69 37Q73 52 50 55Q26 54 29 35Z" fill="#e0caa4"/>' +
        '<path d="m43 27 2 7m4-8 1 7m5-6-2 7" stroke="#a68b65" stroke-width="2" stroke-linecap="round"/>' +
        '<path d="M35 40q4-5 8 0M55 40q4-5 8 0" fill="none" stroke="#4f6349" stroke-width="1.8" stroke-linecap="round"/>' +
        '<path d="m47 44 3 3 3-3Z" fill="#ac8270"/><path d="M50 47q-3 4-6 1m6-1q3 4 6 1" fill="none" stroke="#8d7557" stroke-width="1" stroke-linecap="round"/>' +
        '<path d="m35 46-12-2m12 6-11 2M64 46l12-2m-12 6 11 2" stroke="#b29d78" stroke-width="1" stroke-linecap="round"/>' +
        '<path d="M40 57v11m16-11v11" stroke="#b39a73" stroke-width="1.4" stroke-linecap="round"/>' +
        '<path d="M31 68q7-5 14 0m5 0q7-5 14 0" fill="none" stroke="#eee0be" stroke-width="3" stroke-linecap="round"/>'
    }
  };

  function renderVisitor(kind) {
    if (typeof kind !== 'string' || !Object.prototype.hasOwnProperty.call(visitors, kind)) {
      throw new RangeError('未知的温室访客。');
    }
    var visitor = visitors[kind];
    return '<svg xmlns="http://www.w3.org/2000/svg" class="visitor-art" viewBox="0 0 100 80" width="100" height="80" role="img" aria-label="' + visitor.name + '" data-visitor="' + kind + '"><title>' + visitor.name + '</title>' + visitor.art + '</svg>';
  }

  return Object.freeze({ renderVisitor: renderVisitor });
});
