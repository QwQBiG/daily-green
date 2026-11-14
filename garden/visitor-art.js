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
      art: '<ellipse cx="49" cy="70" rx="36" ry="4" fill="#a9987b" opacity=".14"/>' +
        '<path d="M12 62Q19 57 47 58H64Q69 56 70 47Q70 39 78 40Q87 41 83 54L80 61Q89 62 90 66Q76 72 20 68Q9 68 12 62Z" fill="#c5d6a4" stroke="#78866b" stroke-width="1.5"/>' +
        '<path d="M24 65Q40 63 59 65" fill="none" stroke="#eff0cd" stroke-width="2" stroke-linecap="round"/>' +
        '<circle cx="42" cy="46" r="23" fill="#e3bba4" stroke="#aa826d" stroke-width="1.5"/>' +
        '<path d="M43 63C19 64 19 28 43 29C64 30 63 56 44 56C31 56 30 38 43 38C53 38 54 49 44 49" fill="none" stroke="#b88b75" stroke-width="2" stroke-linecap="round"/>' +
        '<path d="M28 33q6-5 12-4" fill="none" stroke="#ffe6d0" stroke-width="2.5" stroke-linecap="round"/>' +
        '<path d="M73 44 70 32M80 44l5-12" fill="none" stroke="#8b9b77" stroke-width="2" stroke-linecap="round"/>' +
        '<g fill="#fff8e8" stroke="#78866b" stroke-width="1"><circle cx="70" cy="31" r="3.5"/><circle cx="85" cy="31" r="3.5"/></g>' +
        '<g fill="#695e50"><circle cx="70.5" cy="31.5" r="1.2"/><circle cx="85.5" cy="31.5" r="1.2"/></g>' +
        '<path d="M75 51q3 4 6 0" fill="none" stroke="#6f755b" stroke-width="1.3" stroke-linecap="round"/>' +
        '<ellipse cx="73" cy="49" rx="2.5" ry="1.6" fill="#e2a199"/><ellipse cx="83" cy="49" rx="2.5" ry="1.6" fill="#e2a199"/>'
    },
    moth: {
      name: '借月光的小飞蛾',
      art: '<path d="M46 39C33 10 11 16 15 35C17 48 32 52 47 47Z" fill="#ded5e9" stroke="#9d91ac" stroke-width="1.3"/>' +
        '<path d="M54 39C67 10 89 16 85 35C83 48 68 52 53 47Z" fill="#ece2ef" stroke="#9d91ac" stroke-width="1.3"/>' +
        '<path d="M45 44C22 43 23 69 37 67Q46 65 49 49Z" fill="#c3c9dc" stroke="#9d91ac" stroke-width="1.3"/>' +
        '<path d="M55 44C78 43 77 69 63 67Q54 65 51 49Z" fill="#d4d5e6" stroke="#9d91ac" stroke-width="1.3"/>' +
        '<g fill="#f8edcf"><ellipse cx="28" cy="32" rx="5" ry="6" transform="rotate(-28 28 32)"/><ellipse cx="72" cy="32" rx="5" ry="6" transform="rotate(28 72 32)"/><circle cx="35" cy="56" r="3"/><circle cx="65" cy="56" r="3"/></g>' +
        '<path d="M23 42q10 5 17 0m20 0q7 5 17 0" fill="none" stroke="#b2a4c3" stroke-width="1.2" stroke-linecap="round"/>' +
        '<ellipse cx="50" cy="46" rx="5" ry="15" fill="#d7bd9c" stroke="#ab967f" stroke-width="1.2"/>' +
        '<circle cx="50" cy="30" r="7" fill="#f7e3be" stroke="#ab967f" stroke-width="1.2"/>' +
        '<path d="M47 24q-1-8-7-9m13 9q1-8 7-9" fill="none" stroke="#a997ae" stroke-width="1.5" stroke-linecap="round"/>' +
        '<g fill="#685c53"><circle cx="47.5" cy="29.5" r="1"/><circle cx="52.5" cy="29.5" r="1"/></g>' +
        '<path d="M48 33q2 2 4 0" fill="none" stroke="#8d7866" stroke-width=".9" stroke-linecap="round"/><g fill="#e6b2af"><circle cx="45" cy="32" r="1.4"/><circle cx="55" cy="32" r="1.4"/></g>'
    },
    ladybird: {
      name: '停在叶边的小瓢虫',
      art: '<ellipse cx="50" cy="69" rx="25" ry="4" fill="#a9987b" opacity=".14"/>' +
        '<path d="M31 38 23 33m8 15-11 1m16 9-9 7M69 38l8-5M69 48l11 1M64 58l9 7" fill="none" stroke="#857c69" stroke-width="2" stroke-linecap="round"/>' +
        '<ellipse cx="50" cy="45" rx="24" ry="25" fill="#eaa096" stroke="#a97b6d" stroke-width="1.5"/>' +
        '<path d="M50 25v44" stroke="#aa7c70" stroke-width="1.5"/>' +
        '<path d="M32 35q3-9 11-9" fill="none" stroke="#ffe1c7" stroke-width="3" stroke-linecap="round"/>' +
        '<g fill="#9e7c6e"><circle cx="37" cy="39" r="4"/><circle cx="63" cy="39" r="4"/><circle cx="37" cy="54" r="3.5"/><circle cx="63" cy="54" r="3.5"/><circle cx="44" cy="63" r="2.3"/><circle cx="56" cy="63" r="2.3"/></g>' +
        '<path d="M42 24q-4-8-9-8m25 8q4-8 9-8" fill="none" stroke="#8d957c" stroke-width="1.8" stroke-linecap="round"/>' +
        '<ellipse cx="50" cy="25" rx="12" ry="10" fill="#acba96" stroke="#78866b" stroke-width="1.3"/>' +
        '<g fill="#665d50"><circle cx="46" cy="24" r="1.4"/><circle cx="54" cy="24" r="1.4"/></g>' +
        '<path d="M48 29q2 2 4 0" fill="none" stroke="#6e725c" stroke-width="1.1" stroke-linecap="round"/>' +
        '<g fill="#e3a9a0"><ellipse cx="42" cy="28" rx="2.2" ry="1.5"/><ellipse cx="58" cy="28" rx="2.2" ry="1.5"/></g>'
    },
    cat: {
      name: '来窗边打盹的小猫',
      art: '<ellipse cx="50" cy="71" rx="35" ry="4" fill="#a9987b" opacity=".14"/>' +
        '<path d="M72 64Q96 67 90 45Q87 37 81 42Q77 47 84 51Q88 60 73 58" fill="#e4c6a4" stroke="#b09278" stroke-width="1.5"/>' +
        '<path d="M28 68Q20 50 34 42Q50 34 66 45Q79 53 74 68Z" fill="#ecd5b5" stroke="#b09278" stroke-width="1.5"/>' +
        '<path d="M29 38 27 18Q36 17 43 26M55 26Q63 17 71 18L69 39" fill="#f5e2c6" stroke="#b09278" stroke-width="1.5" stroke-linejoin="round"/>' +
        '<path d="m31 23 3 12 7-6m25-6-3 12-6-6" fill="#e9b4ab"/>' +
        '<path d="M28 36Q30 26 48 26Q67 24 70 37Q74 55 50 57Q25 55 28 36Z" fill="#f8e6cc" stroke="#b09278" stroke-width="1.5"/>' +
        '<path d="m43 28 2 6m5-7v6m6-5-2 6" stroke="#cbaa88" stroke-width="2.4" stroke-linecap="round"/>' +
        '<path d="M35 41q4-5 8 0M55 41q4-5 8 0" fill="none" stroke="#756551" stroke-width="1.7" stroke-linecap="round"/>' +
        '<g fill="#e4aea5"><ellipse cx="34" cy="46" rx="4" ry="2.3"/><ellipse cx="65" cy="46" rx="4" ry="2.3"/></g>' +
        '<path d="m47 45 3 3 3-3Z" fill="#c9968d"/><path d="M50 48q-3 4-6 1m6-1q3 4 6 1" fill="none" stroke="#9c8168" stroke-width="1" stroke-linecap="round"/>' +
        '<path d="m34 46-11-2m11 6-10 2m42-6 11-2m-11 6 10 2" stroke="#b99d7d" stroke-width="1" stroke-linecap="round"/>' +
        '<path d="M38 59v10m21-10v10" stroke="#c4a88b" stroke-width="1.3" stroke-linecap="round"/><path d="M32 69q6-4 12 0m10 0q6-4 12 0" fill="none" stroke="#fff1da" stroke-width="3" stroke-linecap="round"/>'
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
