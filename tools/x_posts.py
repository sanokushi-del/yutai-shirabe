#!/usr/bin/env python3
"""C-10 X（旧 Twitter）に投稿する文と、note の記事の下書きを作る。

  python tools/x_posts.py                    # 今日から30日分（drafts/ に書き出す）
  python tools/x_posts.py --days 30          # 30日分
  python tools/x_posts.py --note 2027-03     # 2027年3月権利の note 下書きも作る

書き出し先の drafts/ は公開しない（.gitignore に入れてある）。投稿は手で行う。
URL を付けると、リンク先の共有用画像（会社ごとの OG 画像）がカードとして出る。
"""
import argparse
import datetime
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pplib import ROOT, DATA, clean_tdnet_name, config, jp_date, load_companies, load_json, shorten_company_name, today_jst, x_weighted_length  # noqa: E402

LIMIT = 280
TAG = "#株主優待"


def fit(head, bullets, tail):
    """X の文字数（280）に収まるだけ、bullets を入れる。"""
    used, rest = [], len(bullets)
    for b in bullets:
        more = rest - len(used) - 1
        trial = "\n".join([head] + used + [b] + ([f"ほか{more}社"] if more > 0 else []) + [tail])
        if x_weighted_length(trial) > LIMIT:
            break
        used.append(b)
    more = len(bullets) - len(used)
    return "\n".join([head] + used + ([f"ほか{more}社"] if more > 0 else []) + [tail])


def last_day_posts(companies, start, days, site_url):
    by_day = {}
    for c in companies:
        if c.get("d"):
            by_day.setdefault(c["d"], []).append(c)
    out = []
    for i in range(days + 1):
        d = start + datetime.timedelta(days=i)
        cs = by_day.get(d.isoformat())
        if not cs:
            continue
        cs = sorted(cs, key=lambda c: (-(c.get("y") or 0), c["c"]))
        n100 = sum(1 for c in cs if c.get("s") and c["s"] <= 100)
        head = (f"【{jp_date(d)}は株主優待の権利付き最終日】\n"
                f"この日の大引けまでの買いで権利がとれる会社：{len(cs)}社（100株以下 {n100}社）")
        bullets = []
        for c in cs:
            kind = c.get("p") or "・".join(c.get("k") or []) or "優待"
            bullets.append(f"・{shorten_company_name(c['n'])}（{c['c']}）{kind}")
        url = f"{site_url}/calendar/{d.strftime('%Y-%m')}.html#d-{d.isoformat()}"
        tail = f"一覧→ {url}\n{TAG}"
        text = fit(head, bullets, tail)
        post_on = d - datetime.timedelta(days=1)
        out.append((f"権利付き最終日 {d.isoformat()}（投稿の目安：前日 {post_on.isoformat()} の夜か当日の朝）", text))
    return out


def company_posts(companies, start, days, site_url, limit):
    soon = [c for c in companies if c.get("d") and start.isoformat() <= c["d"] <= (start + datetime.timedelta(days=days)).isoformat()]
    with_photo = [c for c in soon if (ROOT / "assets" / "benefits" / f"{c['c']}-01.webp").exists()]
    with_photo.sort(key=lambda c: (c["d"], -(c.get("y") or 0)))
    out = []
    for c in with_photo[:limit]:
        name = shorten_company_name(c["n"])
        months = "・".join(f"{m}月" for m in c.get("m") or [])
        lines = [f"{name}（{c['c']}）の株主優待", f"もらえる品の種類：{c.get('p') or '・'.join(c.get('k') or [])}"]
        cond = [f"権利確定月 {months}"] if months else []
        if c.get("s"):
            cond.append(f"必要株数 {c['s']:,}株")
        if c.get("y"):
            cond.append(f"年額の推定 {c['y']:,}円相当")
        if cond:
            lines.append(" / ".join(cond))
        if c.get("h"):
            lines.append(f"継続保有 {c['h']}")
        lines.append(f"次の権利付き最終日：{jp_date(c['d'])}")
        lines.append(f"{site_url}/c/{c['c']}.html")
        lines.append(TAG)
        out.append((f"会社の紹介 {c['c']}（権利付き最終日 {c['d']}）", "\n".join(lines)))
    return out


def news_posts(news, start, site_url, names):
    out = []
    since = (start - datetime.timedelta(days=14)).isoformat()
    for e in sorted(news, key=lambda e: e["date"], reverse=True):
        if e["date"] < since:
            continue
        name = names.get(e["code"], clean_tdnet_name(e.get("name", "")))
        head = [f"【株主優待の{e['kind']}】{name}（{e['code']}）", e["title"]]
        tail = []
        if (ROOT / f"c/{e['code']}.html").exists():
            tail.append(f"条件の一覧→ {site_url}/c/{e['code']}.html")
        if e.get("source_url"):
            tail.append(f"出典→ {e['source_url']}")
        tail.append(TAG)
        summary = e.get("summary") or ""
        # 280 字に収まるまで要約を短くする（入らなければ要約なし、それでも長ければ出典を外す）
        while True:
            body = head + ([summary + ("…" if summary != (e.get("summary") or "") else "")] if summary else []) + tail
            if x_weighted_length("\n".join(body)) <= LIMIT:
                break
            if summary:
                summary = summary[:-4] if len(summary) > 8 else ""
            elif any(t.startswith("出典→") for t in tail):
                tail = [t for t in tail if not t.startswith("出典→")]
            else:
                break
        lines = body
        out.append((f"お知らせ {e['date']} {e['code']}", "\n".join(lines)))
    return out


def note_draft(companies, ym, site_url):
    y, m = (int(x) for x in ym.split("-"))
    cs = [c for c in companies if m in (c.get("m") or [])]
    n100 = sum(1 for c in cs if c.get("s") and c["s"] <= 100)
    no_hold = sum(1 for c in cs if not c.get("h"))
    kinds = Counter(k for c in cs for k in (c.get("k") or []))
    top = sorted([c for c in cs if c.get("y")], key=lambda c: -c["y"])[:10]
    last_days = Counter(c["d"] for c in cs if c.get("d", "").startswith(ym))
    lines = [f"# {y}年{m}月権利の株主優待まとめ（{len(cs)}社）", "",
             f"{y}年{m}月に権利確定日（基準日）がある株主優待は **{len(cs)}社** です。"
             f"有価証券報告書の特典欄から読み取った「優待しらべ」のデータで数えました（推定を含みます）。", ""]
    if last_days:
        main_day, cnt = last_days.most_common(1)[0]
        lines += [f"- 権利付き最終日：**{jp_date(main_day, True)}**（{cnt}社）", ""]
    lines += ["## 数字で見る", "",
              f"- 100株以下で始められる会社：{n100}社",
              f"- 継続保有の条件の記載がない会社：{no_hold}社",
              "- 優待の種類（1社が複数に入ります）：" + "、".join(f"{k} {v}社" for k, v in kinds.most_common(6)), "",
              "## 優待の年額の推定が多い会社（上位10社）", "",
              "| 会社 | 必要株数 | 年額の推定 |", "|---|---|---|"]
    for c in top:
        lines.append(f"| [{shorten_company_name(c['n'])}（{c['c']}）]({site_url}/c/{c['c']}.html) | "
                     f"{(str(c['s']) + '株') if c.get('s') else '記載なし'} | {c['y']:,}円相当 |")
    lines += ["", "## 一覧", "",
              f"- {m}月に株主優待がもらえる会社の一覧：{site_url}/list/month-{m:02d}.html",
              f"- {m}月権利の優待利回りの高い順：{site_url}/rank/month-{m:02d}.html",
              f"- {y}年{m}月の権利付き最終日カレンダー：{site_url}/calendar/{y}-{m:02d}.html", "",
              "※ 値は有価証券報告書から規則で読み取った推定を含みます。正式な内容は各社の発表でご確認ください。"
              "投資の勧誘・助言ではありません。", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--start", help="始めの日（YYYY-MM-DD）。省くと今日")
    ap.add_argument("--note", help="note の下書きを作る権利月（YYYY-MM）")
    ap.add_argument("--companies", type=int, default=8, help="会社の紹介の数")
    ap.add_argument("--out", default=str(ROOT / "drafts"))
    args = ap.parse_args()
    cfg = config()
    site_url = cfg.get("site_url", "https://yutai-shirabe.com")
    start = datetime.date.fromisoformat(args.start) if args.start else today_jst()
    companies = load_companies()
    names = {c["c"]: shorten_company_name(c["n"]) for c in companies}
    news = load_json(DATA / "news.json", [])

    sections = [("お知らせ（新設・変更・廃止）", news_posts(news, start, site_url, names)),
                ("権利付き最終日", last_day_posts(companies, start, args.days, site_url)),
                ("会社の紹介（写真のある会社）", company_posts(companies, start, max(args.days, 45), site_url, args.companies))]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    md = [f"# X の投稿文（{start.isoformat()} から {args.days} 日）", "",
          "そのまま貼れる文です。文字数は X の数え方（URL は23字、日本語は2字）で 280 以内に収めています。", ""]
    for title, posts in sections:
        md += [f"## {title}", ""]
        if not posts:
            md += ["（ありません）", ""]
        for label, text in posts:
            md += [f"### {label}（{x_weighted_length(text)}/280）", "", "```", text, "```", ""]
    p = out_dir / f"x-posts-{start.isoformat()}.md"
    p.write_text("\n".join(md), encoding="utf-8")
    print(f"書き出し: {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}")
    if args.note:
        q = out_dir / f"note-{args.note}.md"
        q.write_text(note_draft(companies, args.note, site_url), encoding="utf-8")
        print(f"書き出し: {q.relative_to(ROOT) if q.is_relative_to(ROOT) else q}")


if __name__ == "__main__":
    main()
