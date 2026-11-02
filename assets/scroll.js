(function () {
  'use strict';
  // ランキングページ等のスクロール位置・アンカー吸着復元。
  // スマホで会社個別ページに遷移後、「戻る」ボタンを押した際に直前にタップした会社の直前に正確に吸着復元する。
  // history.scrollRestoration = 'manual' でブラウザの誤ったネイティブスクロール上書き（真ん中に戻される現象）を防止。
  if ('scrollRestoration' in history) {
    try { history.scrollRestoration = 'manual'; } catch (e) {}
  }

  function getStore() {
    try {
      if (window.name && window.name.indexOf('{') === 0) {
        var d = JSON.parse(window.name);
        if (d && typeof d === 'object') { return d; }
      }
    } catch (e) {}
    return {};
  }
  function setStore(k, v) {
    try {
      var s = getStore();
      s[k] = v;
      window.name = JSON.stringify(s);
    } catch (e) {}
  }
  function getElTop(el) {
    var top = 0;
    while (el) { top += el.offsetTop || 0; el = el.offsetParent; }
    return top;
  }
  function savePos(code) {
    try {
      var p = location.pathname + location.search;
      var y = window.pageYOffset || window.scrollY || 0;
      var s = getStore();
      var prev = s[p] || {};
      setStore(p, { y: y, c: code || prev.c || null });
    } catch (e) {}
  }
  function handleLinkTouch(e) {
    var t = e.target;
    while (t && t !== document.body) {
      if (t.tagName === 'A' && t.href) {
        var m = /\/c\/([0-9A-Z]{4})\.html/.exec(t.href);
        if (m) { savePos(m[1]); }
        break;
      }
      t = t.parentNode;
    }
  }
  document.addEventListener('touchstart', handleLinkTouch, { passive: true });
  document.addEventListener('pointerdown', handleLinkTouch, { passive: true });
  document.addEventListener('click', handleLinkTouch, { passive: true });
  window.addEventListener('pagehide', function () { savePos(null); });

  function restorePos() {
    try {
      if ('scrollRestoration' in history) {
        try { history.scrollRestoration = 'manual'; } catch (e) {}
      }
      var p = location.pathname + location.search;
      var store = getStore();
      var data = store[p];
      if (data) {
        function doScroll() {
          if (data.c) {
            var el = document.querySelector('a[href*="' + data.c + '.html"]');
            if (el) {
              var target = el;
              var curEl = el;
              while (curEl && curEl !== document.body) {
                if (curEl.tagName === 'TR') { target = curEl; break; }
                curEl = curEl.parentNode;
              }
              var top = getElTop(target);
              var offset = Math.round(window.innerHeight * 0.28);
              var targetY = Math.max(0, top - offset);
              window.scrollTo(0, targetY);
              return;
            }
          }
          if (typeof data.y === 'number' && data.y > 0) {
            window.scrollTo(0, data.y);
          }
        }
        doScroll();
        requestAnimationFrame(doScroll);
        setTimeout(doScroll, 20);
        setTimeout(doScroll, 80);
        setTimeout(doScroll, 180);
        setTimeout(doScroll, 350);
        setTimeout(doScroll, 600);
        setTimeout(doScroll, 1000);
      }
    } catch (e) {}
  }
  restorePos();
  window.addEventListener('pageshow', restorePos);
  window.addEventListener('load', restorePos);
})();
