(function () {
  'use strict';
  // 条件で探す欄。assets/companies.js の一覧を、ブラウザの中で絞り込む（どこにも送らない・保存しない）。
  var data = window.YUTAI_COMPANIES || [];
  function $(id) { return document.getElementById(id); }
  var out = $('f-results');
  if (!out) { return; }
  var FIRST = 100;
  var shown = FIRST;
  var matched = [];
  var f = { text: $('f-text'), month: $('f-month'), shares: $('f-shares'), hold: $('f-hold'), cat: $('f-cat'),
            amount: $('f-amount'), sort: $('f-sort'), dir: $('f-dir') };
  function norm(s) { return String(s).normalize('NFKC').toLowerCase().replace(/\s+/g, ''); }
  function num(s) {
    var t = String(s).normalize('NFKC').replace(/[,\s]/g, '');
    return /^\d+$/.test(t) ? parseInt(t, 10) : NaN;
  }
  data.forEach(function (c) { c._t = norm(c.c + c.n); });
  function pass(c, q) {
    if (q.text && c._t.indexOf(q.text) < 0) { return false; }
    if (q.month && c.m.indexOf(q.month) < 0) { return false; }
    if (!isNaN(q.shares) && !(c.s !== null && c.s <= q.shares)) { return false; }
    if (q.hold === 'required' && !c.h) { return false; }
    if (q.hold === 'longterm' && c.l !== 1) { return false; }
    if (q.hold === 'none' && (c.h || c.l === 1)) { return false; }
    if (q.cat && c.k.indexOf(q.cat) < 0) { return false; }
    if (!isNaN(q.amount) && !(c.y !== null && c.y >= q.amount)) { return false; }
    return true;
  }
  function key(c, by) {
    if (by === 'next') { return c.d === '' ? null : c.d; }
    if (by === 'shares') { return c.s; }
    if (by === 'amount') { return c.y; }
    return c.c;
  }
  function sortBy(list, by, desc) {
    list.sort(function (a, b) {
      var x = key(a, by), y = key(b, by);
      if (x === null && y === null) { return a.c < b.c ? -1 : 1; }
      if (x === null) { return 1; }
      if (y === null) { return -1; }
      if (x === y) { return a.c < b.c ? -1 : 1; }
      return (x < y ? -1 : 1) * (desc ? -1 : 1);
    });
  }
  function cell(row, text) { var td = document.createElement('td'); td.textContent = text; row.appendChild(td); return td; }
  function render() {
    out.textContent = '';
    var table = document.createElement('table');
    var head = document.createElement('tr');
    ['コード', '会社名', '基準日', '次の権利付き最終日', '必要株数', '継続保有', '主な種類', '年額の推定'].forEach(function (h) {
      var th = document.createElement('th'); th.scope = 'col'; th.textContent = h; head.appendChild(th);
    });
    var thead = document.createElement('thead'); thead.appendChild(head); table.appendChild(thead);
    var tbody = document.createElement('tbody');
    matched.slice(0, shown).forEach(function (c) {
      var tr = document.createElement('tr');
      cell(tr, c.c);
      var td = document.createElement('td'); var a = document.createElement('a');
      a.href = 'c/' + c.c + '.html'; a.textContent = c.n; td.appendChild(a); tr.appendChild(td);
      cell(tr, c.b || '—');
      cell(tr, c.d || '—');
      cell(tr, c.s === null ? '—' : c.s.toLocaleString('ja-JP') + '株');
      cell(tr, c.h || (c.l === 1 ? '長期優遇' : '—'));
      cell(tr, c.p || '—');
      cell(tr, c.y === null ? '—' : c.y.toLocaleString('ja-JP') + '円').className = 'num';
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    var wrap = document.createElement('div'); wrap.className = 'table-wrap'; wrap.setAttribute('role', 'region');
    wrap.setAttribute('aria-label', '絞り込みの結果'); wrap.tabIndex = 0; wrap.appendChild(table);
    if (matched.length) { out.appendChild(wrap); }
    $('f-count').textContent = matched.length.toLocaleString('ja-JP') + '社が当てはまります（全' + data.length.toLocaleString('ja-JP') + '社）。' +
      (matched.length > shown ? ' 先頭の' + shown.toLocaleString('ja-JP') + '社を表示しています。' : '');
    var more = $('f-more');
    more.hidden = matched.length <= shown;
    more.textContent = 'さらに表示（残り' + Math.max(0, matched.length - shown).toLocaleString('ja-JP') + '社）';
  }
  function update() {
    var q = { text: norm(f.text.value), month: f.month.value === '' ? 0 : parseInt(f.month.value, 10), shares: num(f.shares.value),
              hold: f.hold.value, cat: f.cat.value, amount: num(f.amount.value) };
    matched = data.filter(function (c) { return pass(c, q); });
    sortBy(matched, f.sort.value, f.dir.value === 'desc');
    shown = FIRST;
    render();
  }
  Object.keys(f).forEach(function (k) { f[k].addEventListener('input', update); f[k].addEventListener('change', update); });
  $('f-reset').addEventListener('click', function () {
    f.text.value = ''; f.shares.value = ''; f.amount.value = '';
    f.month.value = ''; f.hold.value = ''; f.cat.value = ''; f.sort.value = 'code'; f.dir.value = 'asc';
    update();
  });
  $('f-more').addEventListener('click', function () { shown += FIRST; render(); });
  update();
})();
