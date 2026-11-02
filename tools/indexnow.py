#!/usr/bin/env python3
"""C-1 IndexNow で、変わったページを検索エンジン（Bing など）に知らせる。

  python tools/indexnow.py                 # 直前のコミット（HEAD~1..HEAD）で変わったページ
  python tools/indexnow.py --base <rev>    # <rev>..HEAD で変わったページ
  python tools/indexnow.py --all           # サイトマップのすべての URL
  python tools/indexnow.py --dry-run       # 送らずに URL だけ出す

鍵は tools/config.json の indexnow_key。サイトの根に <鍵>.txt（中身は鍵）を置いておく必要がある
（tools/postprocess.py が作る）。GitHub Actions（.github/workflows/indexnow.yml）から、
GitHub Pages の公開が終わったあとに自動で実行される。
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pplib import ROOT, SKIP_DIRS, config, url_for  # noqa: E402

ENDPOINT = "https://api.indexnow.org/indexnow"


def changed_urls(base, site_url):
    out = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AMR", f"{base}..HEAD"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    urls = []
    for rel in out.splitlines():
        rel = rel.strip()
        if not rel.endswith(".html") or rel.split("/")[0] in SKIP_DIRS or rel == "404.html":
            continue
        p = ROOT / rel
        if not p.exists():
            continue
        if re.search(r'<meta name="robots" content="[^"]*noindex', p.read_text(encoding="utf-8")):
            continue
        urls.append(url_for(rel, site_url))
    return urls


def sitemap_urls():
    text = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", text)


def submit(urls, key, site_url):
    host = re.sub(r"^https?://", "", site_url).rstrip("/")
    for i in range(0, len(urls), 10000):
        body = json.dumps({"host": host, "key": key, "keyLocation": f"{site_url}/{key}.txt",
                           "urlList": urls[i:i + 10000]}).encode("utf-8")
        req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=60) as res:
            print(f"IndexNow: {len(urls[i:i + 10000])} URL を送信（HTTP {res.status}）")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--base", default="HEAD~1")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cfg = config()
    site_url = cfg.get("site_url", "https://yutai-shirabe.com")
    key = cfg.get("indexnow_key")
    if not key:
        sys.exit("tools/config.json に indexnow_key がありません")
    urls = sitemap_urls() if args.all else changed_urls(args.base, site_url)
    if not urls:
        print("送る URL はありません")
        return
    if args.dry_run:
        print("\n".join(urls[:50]))
        print(f"（全 {len(urls)} URL。--dry-run なので送っていません）")
        return
    submit(urls, key, site_url)


if __name__ == "__main__":
    main()
