(function () {
  'use strict';
  // 消した会社ページ（記念優待だけ・優待をやめた会社など）に来た人に、無い理由を伝える。コードは URL から取り、英数字4文字のときだけ文字として入れる。
  var box = document.getElementById('nf-company');
  var slot = document.getElementById('nf-code');
  if (!box || !slot) { return; }
  var m = /^\/c\/([0-9A-Za-z]{4})\.html$/.exec(location.pathname);
  if (!m) { return; }
  slot.textContent = m[1].toUpperCase();
  box.hidden = false;
})();
