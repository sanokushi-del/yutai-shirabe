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
  var HOLD_NONE = "条件の記載なし";     // 継続保有が必須も長期優遇も読めなかった会社の表示（Python の site.HOLD_NONE_TEXT。一覧ページと同じ言い方）
  var YEAR_REASON = {"d": "割引", "p": "ポイント", "n": "記載なし", "o": "上の段のみ", "u": "読み取れず"}; // 年額が無い会社の理由の短い言い方（companies.js の r の値 → 文字。Python の site.YEAR_REASON_SHORT。一覧ページの表と同じ言い方）
  var PER_TIME_HEAD = "1回 ";   // r が t（1回の金額だけ読めた会社）のときの表示「1回 1,000円」の頭。金額は a
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
  // 年額が無い会社（y が null）の表示。理由の種類 r の短い言い方（一覧ページの表と同じ）。1回の金額だけ読めた会社（t）は金額つき。年額の下限の条件には当てはまらない（pass は y が null を通さない）
  function yearReason(c) {
    if (c.r === 't' && typeof c.a === 'number') { return PER_TIME_HEAD + c.a.toLocaleString('ja-JP') + '円'; }
    return YEAR_REASON[c.r] || YEAR_REASON.u;
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
      cell(tr, 5, c.h || (c.l === 1 ? '長期優遇' : HOLD_NONE));
      cell(tr, 6, c.p || '—');
      cell(tr, 7, c.y === null ? yearReason(c) : c.y.toLocaleString('ja-JP') + '円').className = 'num';
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
  function search() {
    var q = { text: norm(f.text.value), month: f.month.value === '' ? 0 : parseInt(f.month.value, 10), shares: num(f.shares.value),
              hold: f.hold.value, cat: f.cat.value, amount: num(f.amount.value) };
    matched = data.filter(function (c) { return pass(c, q); });
    sortBy(matched, f.sort.value, f.dir.value === 'desc');
    shown = FIRST;
    render();
  }
  // --- 条件を URL の # 以降に残す（戻る・共有・ブックマークで条件が戻る）。
  // history.replaceState で今の URL を書き換えるだけ（履歴は増やさない。# 以降はサーバーに送られない。どこにも保存しない）。
  // 条件の # は必ず HASH_HEAD で始める（ページ内リンクの #last-… や #main と取り違えない）。例: #f:m=3&s=100&h=required
  // 読み取る値は確かめる: 選択欄は選択肢にある値だけ、数字の欄は半角の 0-9 だけ、文字の欄は長さの上限つき。欄には .value でしか入れない。
  var HASH_HEAD = '#f:';
  var HASH_MAX = 1000;               // # 以降の長さの上限（これより長いものは条件として読まない）
  var TEXT_MAX = 40;                 // 会社名・コードの欄の文字数の上限
  var NUM_MAX = 999999999;           // 数字の欄の上限（9桁）
  var DEFAULTS = { text: '', month: '', shares: '', hold: '', cat: '', amount: '', sort: 'code', dir: 'asc' };
  var HASH_KEYS = [['q', 'text'], ['m', 'month'], ['s', 'shares'], ['h', 'hold'], ['c', 'cat'], ['a', 'amount'], ['o', 'sort'], ['d', 'dir']];
  function isFilterHash(h) { return String(h).indexOf(HASH_HEAD) === 0; }
  function cleanText(s) {
    return Array.from(String(s).replace(/[\u0000-\u001f\u007f]/g, '')).slice(0, TEXT_MAX).join('').trim();
  }
  function allowed(sel, v) {
    for (var i = 0; i < sel.options.length; i++) { if (sel.options[i].value === v) { return true; } }
    return false;
  }
  // 条件の # → { 欄の名前: 値 }。読めない値・知らないキーは入れない（無視する）
  function parseHash(h) {
    var got = {};
    if (!isFilterHash(h) || h.length > HASH_MAX) { return got; }
    h.slice(HASH_HEAD.length).split('&').slice(0, 16).forEach(function (pair) {
      var at = pair.indexOf('=');
      var name = null;
      HASH_KEYS.forEach(function (k) { if (at > 0 && k[0] === pair.slice(0, at)) { name = k[1]; } });
      if (name === null) { return; }
      var v;
      try { v = decodeURIComponent(pair.slice(at + 1)); } catch (e) { return; }
      if (name === 'text') { v = cleanText(v); }
      else if (name === 'shares' || name === 'amount') {
        if (!/^[0-9]{1,9}$/.test(v)) { return; }
        v = String(parseInt(v, 10));
      } else if (!allowed(f[name], v)) { return; }
      got[name] = v;
    });
    return got;
  }
  function applyHash(h) {
    var got = parseHash(h);
    Object.keys(DEFAULTS).forEach(function (name) {
      f[name].value = Object.prototype.hasOwnProperty.call(got, name) ? got[name] : DEFAULTS[name];
    });
  }
  // 今の欄の値 → 条件の #。既定のままの欄は書かない（全部が既定なら空）
  function hashFromForm() {
    var parts = [];
    HASH_KEYS.forEach(function (k) {
      var name = k[1], v = f[name].value;
      if (name === 'text') { v = cleanText(v); }
      else if (name === 'shares' || name === 'amount') { var n = num(v); v = (!isNaN(n) && n <= NUM_MAX) ? String(n) : ''; }
      if (v === DEFAULTS[name]) { return; }
      try { parts.push(k[0] + '=' + encodeURIComponent(v)); } catch (e) { /* 対になっていないサロゲートなど。その欄は書かない */ }
    });
    return parts.length ? HASH_HEAD + parts.join('&') : '';
  }
  function writeHash(clear) {
    var h = clear ? '' : hashFromForm();
    if (h === location.hash) { return; }
    // 条件が既定のままで、今の # が条件ではない（#last-… などのページ内リンク）なら、そのまま残す
    if (h === '' && !clear && !isFilterHash(location.hash)) { return; }
    try { history.replaceState(null, '', location.pathname + location.search + h); } catch (e) { /* 書き換えられない環境では何もしない */ }
  }
  function onChange() { search(); writeHash(false); }
  // # に条件があれば欄に戻して絞り込む。条件の # でなければ（#last-… など）欄には触らない
  function restore() {
    if (!isFilterHash(location.hash)) { return false; }
    applyHash(location.hash);
    search();
    writeHash(false);                // 読めなかった部分を落とした形に直す
    return true;
  }
  Object.keys(f).forEach(function (k) { f[k].addEventListener('input', onChange); f[k].addEventListener('change', onChange); });
  $('f-reset').addEventListener('click', function () {
    Object.keys(DEFAULTS).forEach(function (name) { f[name].value = DEFAULTS[name]; });
    search();
    writeHash(true);
  });
  $('f-more').addEventListener('click', function () { shown += FIRST; render(); });
  window.addEventListener('hashchange', restore);
  if (!restore()) { search(); }
})();
