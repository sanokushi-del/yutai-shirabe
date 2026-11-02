#!/usr/bin/env python3
"""C-9 株主優待の新設・変更・拡充・廃止のお知らせを tools/data/news.json に足す。

  python tools/add_news.py --date 2026-11-04 --code 1234 --kind 新設 \\
      --title "株主優待制度の新設に関するお知らせ" \\
      --summary "100株以上の株主にQUOカード1,000円分（年1回、3月末）" \\
      --url "https://www.release.tdnet.info/inbs/xxxx.pdf" --label TDnet

足したあとに python tools/postprocess.py を実行すると、お知らせのページ（news/index.html）、
RSS（news/feed.xml）、会社ページの「優待のお知らせ」に出る。
会社の発表を開いて確かめた内容だけを入れること。
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pplib import DATA, ROOT, load_json, save_json  # noqa: E402

KINDS = ["新設", "拡充", "変更", "廃止", "再開", "休止", "その他"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True, help="発表日（YYYY-MM-DD）")
    ap.add_argument("--code", required=True, help="証券コード（例 2702、130A）")
    ap.add_argument("--kind", required=True, choices=KINDS)
    ap.add_argument("--title", required=True, help="発表の題（例：株主優待制度の新設に関するお知らせ）")
    ap.add_argument("--summary", default="", help="内容の要約（自分の言葉で短く）")
    ap.add_argument("--url", default="", help="出典（会社の発表・TDnet の URL）")
    ap.add_argument("--label", default="会社の発表", help="出典の名前（例 TDnet）")
    ap.add_argument("--name", default="", help="会社ページが無い会社のときの社名")
    args = ap.parse_args()

    datetime.date.fromisoformat(args.date)
    code = args.code.upper()
    if not (ROOT / f"c/{code}.html").exists() and not args.name:
        sys.exit(f"c/{code}.html がありません。会社ページが無い会社なら --name で社名を入れてください")
    path = DATA / "news.json"
    news = load_json(path, [])
    entry = {"date": args.date, "code": code, "kind": args.kind, "title": args.title,
             "summary": args.summary, "source_url": args.url, "source_label": args.label}
    if args.name:
        entry["name"] = args.name
    news = [e for e in news if not (e["date"] == args.date and e["code"] == code and e["kind"] == args.kind)]
    news.append(entry)
    news.sort(key=lambda e: (e["date"], e["code"]), reverse=True)
    save_json(path, news)
    print(f"足しました（全 {len(news)} 件）。python tools/postprocess.py を実行してください。")


if __name__ == "__main__":
    main()
