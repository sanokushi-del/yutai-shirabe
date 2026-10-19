(function () {
  'use strict';
  // 条件で探す欄。assets/companies.js の一覧を、ブラウザの中で絞り込む（どこにも送らない・保存しない）。
  var data = window.YUTAI_COMPANIES || [];
  function $(id) { return document.getElementById(id); }
  var out = $('f-results');
  if (!out) { return; }
  var FIRST = 100;
  var THIS_YEAR = 2026;          // サイトを作った日の年（書き出し時に入る）。表の中の日付はこの年なら年を省く
  var HEADERS = ["コード", "会社名", "基準日", "次の権利付き最終日", "必要株数", "継続保有", "主な種類", "年額の推定"];         // 表の見出し。各セルの data-label（スマホのカードの項目名）にも使う
  var NAME_COLUMN = 1;
  var DATES_COLUMN = 2;
  var SHORT = {"次の権利付き最終日": "最終日", "必要株数": "株数", "年額の推定": "年額", "主な種類": "種類"};             // スマホのカードで値の直前に出す短い項目名（data-short）。無い項目は data-label を使う
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
  // "2026-10-28" → 今年なら "10月28日（水）"、別の年なら "2027年1月5日（火）"（Python の fmt_table_date と同じ規則）
  function dateText(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
    if (!m) { return iso; }
    var y = parseInt(m[1], 10), mo = parseInt(m[2], 10), d = parseInt(m[3], 10);
    var wd = '日月火水木金土'.charAt(new Date(Date.UTC(y, mo - 1, d)).getUTCDay());
    return (y === THIS_YEAR ? '' : y + '年') + mo + '月' + d + '日（' + wd + '）';
  }
  function cell(row, i, text) {
    var td = document.createElement('td');
    td.textContent = text;
    td.setAttribute('data-label', HEADERS[i]);
    if (SHORT[HEADERS[i]]) { td.setAttribute('data-short', SHORT[HEADERS[i]]); }
    row.appendChild(td);
    return td;
  }
  function render() {
    out.textContent = '';
    var table = document.createElement('table');
    var head = document.createElement('tr');
    HEADERS.forEach(function (h) {
      var th = document.createElement('th'); th.scope = 'col'; th.textContent = h; head.appendChild(th);
    });
    var thead = document.createElement('thead'); thead.appendChild(head); table.appendChild(thead);
    var tbody = document.createElement('tbody');
    matched.slice(0, shown).forEach(function (c) {
      var tr = document.createElement('tr');
      cell(tr, 0, c.c);
      var td = cell(tr, NAME_COLUMN, ''); var a = document.createElement('a');
      a.href = 'c/' + c.c + '.html'; a.textContent = c.n; td.appendChild(a); td.className = 'name';
      cell(tr, DATES_COLUMN, c.b || '—').className = 'fold';
      cell(tr, 3, c.d ? dateText(c.d) : '—');
      cell(tr, 4, c.s === null ? '—' : c.s.toLocaleString('ja-JP') + '株');
      cell(tr, 5, c.h || (c.l === 1 ? '長期優遇' : '—'));
      cell(tr, 6, c.p || '—');
      cell(tr, 7, c.y === null ? '—' : c.y.toLocaleString('ja-JP') + '円').className = 'num';
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    var wrap = document.createElement('div'); wrap.className = 'table-wrap'; wrap.setAttribute('data-cards', ''); wrap.setAttribute('role', 'region');
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
