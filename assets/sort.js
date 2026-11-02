(function () {
  'use strict';
  // 一覧ページの会社の表の並べ替え（改善案3 U-7）と堅牢なスクロール位置・アンカー吸着復元。
  // 見出しをボタンにして、押すとその列の昇順・降順に並べ替える。
  // スマホの幅（見出しの行が隠れる）では、表の上に選択欄も出す（CSS が幅で出し分ける）。並べ替えはこのページの中だけ。どこにも送らない・保存しない。
  // 並べ替えの種類は見出し(th)の data-sort: code = コードを単純に比べる / text = 日本語の辞書順 / num = セルの data-v を数として / date = セルの data-v の文字列
  var wrap = document.querySelector('.table-wrap[data-sortable]');
  var table = wrap ? wrap.querySelector('table') : null;
  var tbody = table ? table.tBodies[0] : null;
  var heads = table ? Array.prototype.slice.call(table.querySelectorAll('thead th[data-sort]')) : [];
  if (!tbody || !heads.length) { return; }
  // 年額の推定の列は num（data-v だけで比べる）なので、理由の言い方（「割引」「ポイント」「記載なし」「1回 1,000円」など）が出ているセルは data-v が無く、自然に値なしで最後になる。
  // 理由の言い方はここ（文字の列の値なし）に足さない: 主な種類の列には「割引」「ポイント」が本物の値として出るため（改善案4 V-2）。
  // ただし「記載なし」は足す: 主な種類の「記載なし」（改善案6 X-6）は本物の種類ではなく、年額の列は num で data-v だけを見るので影響しない
  var EMPTY = ['', '—', '読み取れず', '条件の記載なし', '記載なし'];             // 文字の列で「値なし」とみなす表示（継続保有の「条件の記載なし」も、今までの「—」と同じく最後）
  var collator = (typeof Intl === 'object' && Intl.Collator) ? new Intl.Collator('ja', { numeric: true }) : null;     // 数は大きさで比べる（「1年」「2年」「10年」の順）
  function compareText(x, y) { return collator ? collator.compare(x, y) : x.localeCompare(y, 'ja', { numeric: true }); }

  var kinds = heads.map(function (th) { return th.getAttribute('data-sort') || 'text'; });
  var labels = heads.map(function (th) { return (th.textContent || '').trim(); });
  var cur = 0;              // 今の並べ替えの列（既定は0列目 = コード順）
  var curDesc = false;       // 今の向き（昇順 false / 降順 true）
  var trs = Array.prototype.slice.call(tbody.rows);
  var rows = trs.map(function (tr, i) {
    var cells = Array.prototype.slice.call(tr.cells);
    var values = heads.map(function (th, j) {
      var td = cells[j];
      if (!td) { return null; }
      var k = kinds[j];
      var raw = (td.textContent || '').trim();
      if (k === 'num') {
        var v = td.getAttribute('data-v');
        return (v !== null && v !== '') ? Number(v) : null;
      }
      if (k === 'date') {
        var d = td.getAttribute('data-v');
        return (d !== null && d !== '') ? d : null;
      }
      return EMPTY.indexOf(raw) >= 0 ? null : raw;
    });
    return { i: i, tr: tr, values: values };
  });

  function compare(a, b, k, desc) {
    var x = a.values[k], y = b.values[k];
    if (x === null && y === null) { return a.i - b.i; }
    if (x === null || y === null) { return x === null ? 1 : -1; }
    var r = 0;
    var kind = kinds[k];
    if (kind === 'num') {
      r = x === y ? 0 : (x < y ? -1 : 1);
    } else if (kind === 'date') {
      r = x === y ? 0 : (x < y ? -1 : 1);
    } else {
      r = compareText(x, y);
    }
    if (r === 0) { return a.i - b.i; }
    return desc ? -r : r;
  }

  heads.forEach(function (th, j) {
    var text = (th.textContent || '').trim();
    th.textContent = '';
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = text;
    b.setAttribute('aria-label', text + 'で並べ替える');
    b.addEventListener('click', function () {
      var desc = (cur === j) ? !curDesc : false;
      choose(j, desc);
    });
    th.appendChild(b);
    th.setAttribute('aria-sort', j === 0 ? 'ascending' : 'none');
  });

  var box = document.createElement('div');
  box.className = 'sort-box';
  var colDiv = document.createElement('div');
  var colLab = document.createElement('label');
  colLab.textContent = '並び順';
  var colSel = document.createElement('select');
  colSel.id = 'sort-column';
  colLab.setAttribute('for', colSel.id);
  labels.forEach(function (l, j) {
    var opt = document.createElement('option');
    opt.value = String(j);
    opt.textContent = l;
    colSel.appendChild(opt);
  });
  colDiv.appendChild(colLab);
  colDiv.appendChild(colSel);

  var dirDiv = document.createElement('div');
  var dirLab = document.createElement('label');
  dirLab.textContent = '向き';
  var dirSel = document.createElement('select');
  dirSel.id = 'sort-direction';
  dirLab.setAttribute('for', dirSel.id);
  var optAsc = document.createElement('option');
  optAsc.value = 'asc';
  optAsc.textContent = '小さい順（昇順）';
  var optDesc = document.createElement('option');
  optDesc.value = 'desc';
  optDesc.textContent = '大きい順（降順）';
  dirSel.appendChild(optAsc);
  dirSel.appendChild(optDesc);
  dirDiv.appendChild(dirLab);
  dirDiv.appendChild(dirSel);

  box.appendChild(colDiv);
  box.appendChild(dirDiv);
  wrap.parentNode.insertBefore(box, wrap);

  colSel.addEventListener('change', function () { choose(Number(colSel.value), dirSel.value === 'desc'); });
  dirSel.addEventListener('change', function () { choose(Number(colSel.value), dirSel.value === 'desc'); });

  var live = document.createElement('div');
  live.className = 'sr-only';
  live.setAttribute('aria-live', 'polite');
  wrap.parentNode.insertBefore(live, wrap.nextSibling);

  function choose(k, desc) {
    cur = k; curDesc = desc;
    var sorted = rows.slice().sort(function (a, b) { return compare(a, b, k, desc); });
    var frag = document.createDocumentFragment();
    sorted.forEach(function (r) { frag.appendChild(r.tr); });
    tbody.appendChild(frag);
    heads.forEach(function (th, j) { th.setAttribute('aria-sort', j === k ? (desc ? 'descending' : 'ascending') : 'none'); });
    colSel.value = String(k);
    dirSel.value = desc ? 'desc' : 'asc';
    live.textContent = labels[k] + 'の' + (desc ? '降順' : '昇順') + 'に並べました';
  }
  colSel.value = String(cur);
  dirSel.value = curDesc ? 'desc' : 'asc';

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
  function saveSortPos(code) {
    try {
      var p = location.pathname + location.search;
      var y = window.pageYOffset || window.scrollY || 0;
      var s = getStore();
      var prev = s[p] || {};
      setStore(p, { y: y, k: cur, d: curDesc, c: code || prev.c || null });
    } catch (e) {}
  }
  function handleLinkTouch(e) {
    var t = e.target;
    while (t && t !== document.body) {
      if (t.tagName === 'A' && t.href) {
        var m = /\/c\/([0-9A-Z]{4})\.html/.exec(t.href);
        if (m) { saveSortPos(m[1]); }
        break;
      }
      t = t.parentNode;
    }
  }
  document.addEventListener('touchstart', handleLinkTouch, { passive: true });
  document.addEventListener('pointerdown', handleLinkTouch, { passive: true });
  document.addEventListener('click', handleLinkTouch, { passive: true });
  window.addEventListener('pagehide', function () { saveSortPos(null); });

  function restoreSortPos() {
    try {
      if ('scrollRestoration' in history) {
        try { history.scrollRestoration = 'manual'; } catch (e) {}
      }
      var p = location.pathname + location.search;
      var store = getStore();
      var data = store[p];
      if (data) {
        if (typeof data.k === 'number' && typeof data.d === 'boolean' && (data.k !== cur || data.d !== curDesc)) {
          choose(data.k, data.d);
        }
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
  restoreSortPos();
  window.addEventListener('pageshow', restoreSortPos);
  window.addEventListener('load', restoreSortPos);
})();
