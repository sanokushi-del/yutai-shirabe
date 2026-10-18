(function () {
  'use strict';
  // 優待利回りの計算。入力した株価はこのページの中だけで使う（送信も保存もしない）。
  var box = document.getElementById('yield-box');
  var input = document.getElementById('yield-price');
  var out = document.getElementById('yield-result');
  if (!box || !input || !out) { return; }
  var shares = Number(box.getAttribute('data-shares'));
  var year = Number(box.getAttribute('data-year'));
  var IDLE = '株価を入れると、ここに表示されます。';
  function normalize(s) {
    return s.replace(/[０-９]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0xFEE0); })
            .replace(/．/g, '.').replace(/[,，、\s]/g, '');
  }
  function yen(n) { return Math.round(n).toLocaleString('ja-JP') + '円'; }
  function update() {
    var raw = normalize(input.value);
    var price = /^\d+(\.\d+)?$/.test(raw) ? parseFloat(raw) : NaN;
    if (!(price > 0) || !(shares > 0) || !(year > 0)) { out.textContent = IDLE; return; }
    var cost = price * shares;
    out.textContent = '優待利回りの推定 ' + (year / cost * 100).toFixed(2) + '%（年額の推定 ' + yen(year) + ' ÷ 必要な金額 ' + yen(cost) + '）';
  }
  input.addEventListener('input', update);
  update();
})();
