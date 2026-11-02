(function () {
  'use strict';
  // 権利付き最終日までの日数（改善案10 A-2）。<time datetime="YYYY-MM-DD" data-days-until> の後ろに「あとN日」「今日」「終了」を足す。
  // 日付はページに書いてあるので、JavaScript が無くても日付は読める。日数は日本時間の今日から数える。ブラウザの中だけで計算する（送信も保存もしない）。
  var nodes = document.querySelectorAll('time[data-days-until]');
  if (nodes.length) {
    function todayJapan() {
      try {
        var text = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
        var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
        if (m) { return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])); }
      } catch (e) { /* 下の、ブラウザの日付を使う */ }
      var d = new Date();
      return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate());
    }
    var today = todayJapan();
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(node.getAttribute('datetime') || '');
      if (!m) { continue; }
      var days = Math.round((Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) - today) / 86400000);
      var label = days > 0 ? 'あと' + days + '日' : (days === 0 ? '今日' : '終了');
      var next = node.nextElementSibling;
      var span = (next && next.classList.contains('days-until')) ? next : null;
      if (!span) {
        span = document.createElement('span');
        span.className = 'days-until';
        node.parentNode.insertBefore(span, node.nextSibling);
      }
      span.textContent = label;
    }
  }

  // カレンダーの直近の最終日へのスクロール（改善案11 B-2）とスクロール位置・アンカー吸着復元。
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
        return true;
      }
    } catch (e) {}
    return false;
  }

  var restored = restorePos();
  window.addEventListener('pageshow', restorePos);
  window.addEventListener('load', restorePos);

  var root = document.querySelector('.calendar-body');
  if (!root) { return; }
  var now = root.getAttribute('data-now');
  if (!now) { return; }
  var details = Array.prototype.slice.call(root.querySelectorAll('details.day[data-date]'));
  var target = null;
  for (var i = 0; i < details.length; i++) {
    var d = details[i];
    var date = d.getAttribute('data-date');
    if (date && date >= now) { target = d; break; }
  }
  if (!target) { return; }
  target.setAttribute('open', '');
  target.classList.add('today-target');
  if (!restored && !location.hash) {
    try {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      target.scrollIntoView(true);
    }
  }
})();
