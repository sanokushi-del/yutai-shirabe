(function () {
  'use strict';
  // 一覧ページの会社の表の並べ替え（改善案3 U-7）。見出しをボタンにして、押すとその列の昇順・降順に並べ替える。
  // スマホの幅（見出しの行が隠れる）では、表の上に選択欄も出す（CSS が幅で出し分ける）。並べ替えはこのページの中だけ。どこにも送らない・保存しない。
  // 並べ替えの種類は見出し(th)の data-sort: code = コードを単純に比べる / text = 日本語の辞書順 / num = セルの data-v を数として / date = セルの data-v の文字列
  var wrap = document.querySelector('.table-wrap[data-sortable]');
  var table = wrap ? wrap.querySelector('table') : null;
  var tbody = table ? table.tBodies[0] : null;
  var heads = table ? Array.prototype.slice.call(table.querySelectorAll('thead th[data-sort]')) : [];
  if (!tbody || !heads.length) { return; }
  var EMPTY = ['', '—', '読み取れず'];             // 文字の列で「値なし」とみなす表示
  var collator = (typeof Intl === 'object' && Intl.Collator) ? new Intl.Collator('ja', { numeric: true }) : null;     // 数は大きさで比べる（「1年」「2年」「10年」の順）
  function compareText(x, y) { return collator ? collator.compare(x, y) : x.localeCompare(y, 'ja', { numeric: true }); }

  // 行ごとに、並べ替えに使う値を先に読んでおく（null = 値なし）。i = 書き出されたときの順（コード順）
  function readKey(td, kind) {
    if (!td) { return null; }
    var v = td.getAttribute('data-v');
    if (kind === 'num') {
      if (v === null || v === '') { return null; }
      var n = Number(v);
      return isNaN(n) ? null : n;
    }
    if (kind === 'date') { return (v === null || v === '') ? null : v; }
    var t = td.textContent.replace(/\s+/g, ' ').replace(/^ | $/g, '');
    return EMPTY.indexOf(t) >= 0 ? null : t;
  }
  var kinds = heads.map(function (th) { return th.getAttribute('data-sort'); });
  var rows = Array.prototype.map.call(tbody.rows, function (tr, i) {
    return { tr: tr, i: i, keys: heads.map(function (th, k) { return readKey(tr.cells[th.cellIndex], kinds[k]); }) };
  });

  function compare(a, b, k, desc) {
    var x = a.keys[k], y = b.keys[k];
    if (x === null || y === null) {
      if (x === y) { return a.i - b.i; }
      return x === null ? 1 : -1;                  // 値なしは、昇順でも降順でも常に最後
    }
    var r = kinds[k] === 'text' ? compareText(x, y) : (x < y ? -1 : (x > y ? 1 : 0));
    if (r === 0) { return a.i - b.i; }             // 同じ値の中は、書き出されたコード順のまま
    return desc ? -r : r;
  }

  var cur = 0, curDesc = false;                    // 今の並び（heads の何番目の列か・降順か）。書き出し時はコード順
  heads.forEach(function (th, k) {
    var a = th.getAttribute('aria-sort');
    if (a === 'ascending' || a === 'descending') { cur = k; curDesc = a === 'descending'; }
  });

  // 見出しをボタンに差し替える（JS が無いときはただの見出しのまま）
  var labels = heads.map(function (th) { return th.textContent.replace(/^\s+|\s+$/g, ''); });
  heads.forEach(function (th, k) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = labels[k];
    th.textContent = '';
    th.appendChild(b);
    b.addEventListener('click', function () { choose(k, cur === k ? !curDesc : false); });
  });

  // スマホの幅で使う選択欄（パソコンの幅では CSS が隠す）と、並べ替えたことを知らせる欄（画面には出さない）
  function field(id, text, select) {
    var d = document.createElement('div');
    var l = document.createElement('label');
    l.htmlFor = id; l.textContent = text; select.id = id;
    d.appendChild(l); d.appendChild(select);
    return d;
  }
  function option(value, text) {
    var o = document.createElement('option');
    o.value = value; o.textContent = text;
    return o;
  }
  var colSel = document.createElement('select');
  labels.forEach(function (text, k) { colSel.appendChild(option(String(k), text)); });
  var dirSel = document.createElement('select');
  dirSel.appendChild(option('asc', '昇順'));
  dirSel.appendChild(option('desc', '降順'));
  var box = document.createElement('div');
  box.className = 'sort-box';
  box.appendChild(field('sort-col', '並べ替え', colSel));
  box.appendChild(field('sort-dir', '順序', dirSel));
  var live = document.createElement('p');
  live.className = 'sr';
  live.setAttribute('role', 'status');
  wrap.parentNode.insertBefore(live, wrap);
  wrap.parentNode.insertBefore(box, wrap);
  colSel.addEventListener('change', function () { choose(parseInt(colSel.value, 10), dirSel.value === 'desc'); });
  dirSel.addEventListener('change', function () { choose(parseInt(colSel.value, 10), dirSel.value === 'desc'); });

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
})();
