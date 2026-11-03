#!/usr/bin/env python3
"""C-9 TDnet（適時開示情報閲覧サービス）から、表題に「優待」を含む発表を拾って tools/data/news.json に足す。

  python tools/tdnet_news.py              # 今日と昨日（日本時間）
  python tools/tdnet_news.py --days 7     # 7日前まで
  python tools/tdnet_news.py --dry-run    # 足さずに、拾った発表だけ出す

載せるのは「発表日・会社・種類（表題から判断）・表題・PDF の URL」だけ。要約は自動では書かない
（手で書いた要約があれば、そのまま残す）。GitHub Actions（.github/workflows/tdnet-news.yml）から毎日動く。
"""
import argparse
import datetime
import html as htmllib
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pplib import DATA, ROOT, load_json, save_json, today_jst  # noqa: E402

BASE = "https://www.release.tdnet.info/inbs/"
UA = "Mozilla/5.0 (compatible; yutai-shirabe-news/1.0; +https://yutai-shirabe.com/operator.html)"

# 表題から種類を決める（上から順に当てはめる）
KIND_RULES = [
    ("廃止", r"廃止"),
    ("再開", r"再開|再導入"),
    ("拡充", r"変更（拡充）"),
    ("変更", r"一部変更|内容変更"),
    ("拡充", r"拡充|拡大|増額|充実"),
    ("新設", r"新設|導入|開始"),
    ("休止", r"休止|中止|停止"),
    ("変更", r"変更|改定|見直し"),
]
# 優待の制度の発表でないもの・訂正などは拾わない
SKIP = re.compile(r"訂正|取消|延期のお知らせ|株主優待引当金|発送日|発送時期")


def kind_of(title):
    for kind, rx in KIND_RULES:
        if re.search(rx, title):
            return kind
    return "その他"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    for enc in ("utf-8", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def text(s):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def parse_list(page):
    """一覧の表の行から（時刻, コード, 社名, 表題, PDF の URL）を取り出す。"""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)
        link = re.search(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', row, re.S | re.I)
        if len(cells) < 4 or not link:
            continue
        code5 = next((text(c) for c in cells if re.fullmatch(r"[0-9][0-9A-Z]{3}0", text(c))), None)
        if not code5:
            continue
        idx = [text(c) for c in cells].index(code5)
        name = text(cells[idx + 1]) if idx + 1 < len(cells) else ""
        out.append({"time": text(cells[0]), "code": code5[:4], "name": name,
                    "title": text(link.group(2)), "url": urllib.request.urljoin(BASE, link.group(1))})
    return out


def list_day(d):
    rows = []
    for n in range(1, 30):
        page = fetch(f"{BASE}I_list_{n:03d}_{d.strftime('%Y%m%d')}.html")
        if not page:
            break
        got = parse_list(page)
        if not got:
            break
        rows += got
        time.sleep(1)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=1, help="何日前までを見るか（0 なら今日だけ）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    today = today_jst()
    found = []
    for i in range(args.days + 1):
        d = today - datetime.timedelta(days=i)
        rows = list_day(d)
        print(f"{d}: 発表 {len(rows)} 件")
        for r in rows:
            if "優待" in r["title"] and not SKIP.search(r["title"]):
                found.append((d.isoformat(), r))

    path = DATA / "news.json"
    news = load_json(path, [])
    known = {e.get("source_url") for e in news}
    added = 0
    for date, r in found:
        print(f"  {date} {r['code']} {r['name']}：{r['title']}")
        if r["url"] in known:
            continue
        e = {"date": date, "code": r["code"], "kind": kind_of(r["title"]), "title": r["title"],
             "summary": "", "source_url": r["url"], "source_label": "TDnet", "auto": True}
        if not (ROOT / f"c/{r['code']}.html").exists():
            e["name"] = r["name"]
        news.append(e)
        known.add(r["url"])
        added += 1
    if args.dry_run:
        print(f"足す候補: {added} 件（--dry-run なので足していません）")
        return
    if added:
        news.sort(key=lambda e: (e["date"], e["code"]), reverse=True)
        save_json(path, news)
    print(f"足した件数: {added}")


if __name__ == "__main__":
    main()
