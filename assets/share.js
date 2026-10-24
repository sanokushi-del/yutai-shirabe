(function () {
  'use strict';
  // 会社ページの共有（改善案10 A-3）。外部の共有部品は読み込まず、押されたときだけ共有の画面を開く。URL はページの中だけで使う（送信も保存もしない）。
  var box = document.querySelector('.share[data-share-url]');
  if (!box) { return; }
  var url = box.getAttribute('data-share-url') || '';
  if (!/^https?:\/\//.test(url)) { url = location.href; }    // 公開先が決まっていないビルドでは、今のページの URL を使う
  var text = box.getAttribute('data-share-text') || '';
  var status = box.querySelector('.share-status');
  function setStatus(message) { if (status) { status.textContent = message; } }
  function openShare(target) {
    var w = 640, h = 560;
    var left = Math.max(0, Math.round((screen.width - w) / 2));
    var top = Math.max(0, Math.round((screen.height - h) / 2));
    window.open(target, 'share', 'width=' + w + ',height=' + h + ',left=' + left + ',top=' + top + ',noopener');
  }
  function fallbackCopy(value) {
    var area = document.createElement('textarea');
    area.value = value;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(area);
    setStatus(ok ? 'URL をコピーしました。' : 'コピーできませんでした。下の URL を選んでコピーしてください。');
  }
  function copy(value) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(value).then(function () {
        setStatus('URL をコピーしました。');
      }, function () { fallbackCopy(value); });
    } else {
      fallbackCopy(value);
    }
  }
  box.addEventListener('click', function (e) {
    var button = e.target.closest ? e.target.closest('button[data-share]') : null;
    if (!button) { return; }
    var kind = button.getAttribute('data-share');
    if (kind === 'x') {
      openShare('https://twitter.com/intent/tweet?text=' + encodeURIComponent(text) + '&url=' + encodeURIComponent(url));
    } else if (kind === 'line') {
      openShare('https://social-plugins.line.me/lineit/share?text=' + encodeURIComponent(text) + '&url=' + encodeURIComponent(url));
    } else if (kind === 'copy') {
      copy(url);
    }
  });
})();
