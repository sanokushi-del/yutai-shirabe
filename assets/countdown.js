(function () {
  'use strict';
  // 権利付き最終日までの日数（改善案10 A-2）。<time datetime="YYYY-MM-DD" data-days-until> の後ろに「あとN日」「今日」「終了」を足す。
  // 日付はページに書いてあるので、JavaScript が無くても日付は読める。日数は日本時間の今日から数える。ブラウザの中だけで計算する（送信も保存もしない）。
  var nodes = document.querySelectorAll('time[data-days-until]');
  if (!nodes.length) { return; }
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
})();
