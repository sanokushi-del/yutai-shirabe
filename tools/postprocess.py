#!/usr/bin/env python3
"""優待しらべ 後処理（改善案12 C-1〜C-12）。

サイトを作り直した（生成した）あとに実行する。何度実行しても結果は同じ（同じ入力なら差分は出ない）。

  python tools/postprocess.py            # すべて
  python tools/postprocess.py --no-og    # 共有用画像（OG 画像）を作らない
  python tools/postprocess.py --check    # 書き込まずに、変わるファイルの数だけ出す

設定は tools/config.json、手で入れるデータは tools/data/ にある。詳しくは tools/README.md。
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.parse
from email.utils import format_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pplib import (DATA, JST, ROOT, STATE, config, esc, html_files, jp_date, load_json,  # noqa: E402
                   prefix_for, save_json, sha, shorten_company_name, strip_tags, today_jst, url_for)

SUFFIX = " | 優待しらべ"
WEBCAL = "webcal://yutai-shirabe.com/calendar/yutai.ics"


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# ファイルの読み書き
# ---------------------------------------------------------------------------
class Site:
    def __init__(self):
        self.orig, self.text = {}, {}

    def exists(self, rel):
        return rel in self.text or (ROOT / rel).exists()

    def get(self, rel):
        if rel not in self.text:
            with open(ROOT / rel, encoding="utf-8", newline="") as f:
                t = f.read()
            self.orig[rel] = t
            self.text[rel] = t
        return self.text[rel]

    def put(self, rel, t):
        if rel not in self.text:
            if (ROOT / rel).exists():
                self.get(rel)
            else:
                self.orig[rel] = None
        self.text[rel] = t

    def changed(self):
        return [r for r, t in self.text.items() if t != self.orig.get(r)]

    def flush(self):
        n = 0
        for rel in self.changed():
            p = ROOT / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(self.text[rel])
            n += 1
        return n


# ---------------------------------------------------------------------------
# head の部品
# ---------------------------------------------------------------------------
def get_title(h):
    m = re.search(r"<title>(.*?)</title>", h, re.S)
    t = m.group(1) if m else ""
    return t[: -len(SUFFIX)] if t.endswith(SUFFIX) else t


def set_title(h, raw_title):
    return re.sub(r"<title>.*?</title>", lambda m: "<title>" + raw_title + "</title>", h, count=1, flags=re.S)


def get_meta(h, attr, name):
    m = re.search(r'<meta %s="%s" content="([^"]*)">' % (attr, re.escape(name)), h)
    return m.group(1) if m else None


def set_meta(h, attr, name, raw_content):
    rx = re.compile(r'(<meta %s="%s" content=")[^"]*(">)' % (attr, re.escape(name)))
    return rx.sub(lambda m: m.group(1) + raw_content + m.group(2), h, count=1)


def set_all_titles(h, raw_full_title):
    h = set_title(h, raw_full_title)
    h = set_meta(h, "property", "og:title", raw_full_title)
    h = set_meta(h, "name", "twitter:title", raw_full_title)
    return h


def set_all_descriptions(h, raw_desc):
    h = set_meta(h, "name", "description", raw_desc)
    h = set_meta(h, "property", "og:description", raw_desc)
    h = set_meta(h, "name", "twitter:description", raw_desc)
    return h


def insert_after_viewport(h, tag):
    return re.sub(r'(<meta name="viewport"[^>]*>)', lambda m: m.group(1) + "\n" + tag, h, count=1)


def set_h1(h, inner_html, attrs=""):
    return re.sub(r"<h1[^>]*>.*?</h1>", lambda m: f"<h1{attrs}>{inner_html}</h1>", h, count=1, flags=re.S)


def is_noindex(h):
    m = re.search(r'<meta name="robots" content="([^"]*)">', h)
    return bool(m and "noindex" in m.group(1))


def dl_value(h, label):
    m = re.search(r"<dt>" + re.escape(label) + r"</dt>\s*<dd>(.*?)</dd>", h, re.S)
    return strip_tags(m.group(1)) if m else ""


def global_replace(site, mapping, files):
    """mapping の古い文言を新しい文言に、files のすべてで置き換える（数字の直後は置き換えない）。"""
    if not mapping:
        return 0
    items = sorted(mapping.items(), key=lambda kv: -len(kv[0]))
    rx = re.compile(r"(?<![0-9０-９])(" + "|".join(re.escape(k) for k, _ in items) + r")")
    table = dict(items)
    n = 0
    for rel in files:
        h = site.get(rel)
        nh = rx.sub(lambda m: table[m.group(1)], h)
        if nh != h:
            site.put(rel, nh)
            n += 1
    return n


# ---------------------------------------------------------------------------
# C-5 会社ページの定型文を短くする（全文は method.html の「会社ページの補足」と「項目の意味」へ）
# ---------------------------------------------------------------------------
BOILERPLATE = [
    (r'<p class="small summary-note">いずれも有価証券報告書の特典欄から規則で読み取った推定を含みます。詳しくは下の表と出典をご覧ください。必要株数・基準日の「記載なし」は.*?</p>',
     '<p class="small summary-note">いずれも有価証券報告書の特典欄から規則で読み取った推定を含みます。詳しくは下の表と出典をご覧ください。「記載なし」「読み取れず」の意味は<a href="../method.html#terms">項目の意味</a>にまとめています。</p>'),
    (r'<p class="small about-note">業種は東証33業種の区分で、会社の主力事業とは限りません。会社のサイトは、有報の「公告掲載URL」に記載されたものです。(.*?)</p>',
     r'<p class="small about-note">\1業種と会社のサイトの決め方は<a href="../method.html#read-company">会社ページの補足</a>にあります。</p>'),
    (r'<p class="small">株価と、有価証券報告書・決算短信の予想から計算した値です。株価は日々変わります。割安・割高や売買を判断するものではありません。</p>\s*<p class="small">計算式: 最低投資額.*?</p>\s*<p class="small">出典: J-Quants API の株価と財務の要約を.*?</p>',
     '<p class="small">株価と、有価証券報告書・決算短信の予想から計算した値です。株価は日々変わります。割安・割高や売買を判断するものではありません。計算式は<a href="../method.html#market">計算の決め方</a>、出典は<a href="../sources.html#market">出典のページ</a>にあります。</p>'),
    (r'<p class="small">\d{4}-\d{2}-\d{2}以降に権利付き最終日が来る権利確定日（基準日）を、日付順に最大2回分出しています。.*?</p>',
     '<p class="small">権利付き最終日までに株式を保有していることが、権利確定日（基準日）の株主になる条件の目安です（<a href="../guide/rights-last-day.html">数え方</a>）。基準日は推定を含みます。表の決め方は<a href="../method.html#read-company">会社ページの補足</a>にあります。</p>'),
    (r'<p class="small">金額は、特典欄に書かれた金額・枚数・ポイントの換算から規則で出した推定です。.*?</p>',
     '<p class="small">金額は、特典欄に書かれた金額・枚数・ポイントの換算から規則で出した推定です。決め方と、年額を出せないときの理由の意味は<a href="../method.html#terms">項目の意味</a>にあります。</p>'),
    (r'(<div id="yield-box"[^>]*><h3>[^<]*</h3>)<p>株価（1株あたり）を入れると、.*?</p>',
     r'\1<p>株価（1株あたり）を入れると、年額の推定を「株価 × 必要株数」で割った優待利回りを表示します。計算はお使いのブラウザの中だけで行い、入力した値は送らず、保存もしません。</p>'),
    (r'<p class="small">加工・推定を含みます。特典欄の文章は提出会社が書いたものなので、このサイトには転載していません。',
     '<p class="small">加工・推定を含みます。'),
    (r'<p class="small">X・LINE の共有ボタンと、URL のコピーです。外部の共有部品は読み込んでいません。</p>', ''),
    (r'<p class="small">同じ権利月の会社から、主な種類が同じ会社を先に並べています（足りないときは同じ月の会社）。必要株数・種類は有価証券報告書から読み取った推定を含みます。</p>', ''),
]
BOILERPLATE = [(re.compile(a, re.S), b) for a, b in BOILERPLATE]

METHOD_SECTION = """<h2 id="read-company">会社ページの補足</h2>
<p>会社ページの各欄の決め方です。どの会社のページでも同じなので、ここにまとめています。</p>
<ul>
<li><strong>題と見出しの社名</strong>：題と見出しでは「株式会社」を省き、社名と違う店名・ブランド名でよく知られている会社は括弧で添えています。正式な社名は「優待の条件」の表の「社名」にあります。</li>
<li><strong>業種</strong>：東証33業種の区分です。会社の主力事業とは限りません。</li>
<li><strong>会社のサイト</strong>：有報の「公告掲載URL」に記載されたものです。</li>
<li><strong>次の権利確定日（基準日）の表</strong>：サイトの作成日以降に権利付き最終日が来る権利確定日（基準日）を、日付順に最大2回分出しています。権利確定日は基準日と同じ日で、表の「基準日」の列がそれです。</li>
<li><strong>株価から計算した値</strong>：計算式は上の<a href="#market">株価から計算した値</a>にあります。値を出せないもの（株価・予想・必要株数・年額の推定のいずれかが無いなど）は「—」と出しています。</li>
<li><strong>株数ごとの優待内容</strong>：会社の株主優待ページを運営者が確かめてまとめた表です。表がある会社だけに出し、確かめた日と出典を添えています。有価証券報告書から読み取った値とは別に確かめたものです。</li>
<li><strong>優待利回りの計算欄</strong>：計算はページの中（お使いのブラウザ）だけで行い、入力した値はどこにも送らず、保存もしません。</li>
<li><strong>共有ボタン</strong>：X・LINE の共有ボタンと、URL のコピーです。外部の共有部品は読み込んでいません。</li>
<li><strong>同じ月・同じ種類の会社</strong>：同じ権利月の会社から、主な種類が同じ会社を先に並べています（足りないときは同じ月の会社）。必要株数・種類は推定を含みます。</li>
<li><strong>特典欄の文章</strong>：提出会社が書いたものなので、このサイトには転載していません。原文は EDINET の書類の「株式事務の概要」でご確認ください。</li>
</ul>
"""


# ---------------------------------------------------------------------------
# C-2 / C-5 / C-6 / C-9 / C-12 会社ページ
# ---------------------------------------------------------------------------
def company_description(short, code, items, months, shares, hold, amount, yld, ydate, tier_text):
    head = f"{short}（{code}）の株主優待"
    if items and items not in ("記載なし", "読み取れず"):
        s = head + "は" + items.replace(" / ", "、") + "。"
    else:
        s = head + "。"
    conds = []
    if months and "記載なし" not in months and "読み取れず" not in months:
        conds.append(f"権利確定月は{months}")
    if re.match(r"^[\d,]+株$", shares or ""):
        conds.append(f"必要株数は{shares}")
    if hold.startswith("必須"):
        conds.append("継続保有は" + hold)
    elif hold == "長期優遇":
        conds.append("長期保有の優遇あり")
    if conds:
        s += "、".join(conds) + "。"
    if tier_text:
        s += tier_text + "。"
    money = []
    if re.match(r"^[\d,]+円相当$", amount or ""):
        money.append(f"年額の推定は{amount}")
    if yld and yld.endswith("%") and ydate:
        money.append(f"優待利回り{yld}（{ydate}の終値）")
    if money:
        s += "、".join(money) + "。"
    return s + "有価証券報告書から読み取った推定を含みます。"


def render_tiers(t):
    rows = "".join(f'<tr><td>{esc(r.get("shares", ""))}</td><td>{esc(r.get("content", ""))}</td></tr>' for r in t.get("tiers", []))
    parts = ['<section class="card tiers" id="tiers" data-pp="tiers"><h2>株数ごとの優待内容</h2>']
    facts = []
    if t.get("record"):
        facts.append(f'<dt>権利確定日</dt><dd>{esc(t["record"])}</dd>')
    if t.get("condition"):
        facts.append(f'<dt>保有の条件</dt><dd>{esc(t["condition"])}</dd>')
    if facts:
        parts.append('<dl class="facts">' + "".join(facts) + "</dl>")
    parts.append('<div class="table-wrap" role="region" aria-label="株数ごとの優待内容" tabindex="0"><table>'
                 '<caption class="sr">株数ごとの優待内容</caption><thead><tr><th scope="col">保有株数</th>'
                 f'<th scope="col">優待の内容</th></tr></thead><tbody>{rows}</tbody></table></div>')
    if t.get("notes"):
        parts.append('<ul class="small">' + "".join(f"<li>{esc(n)}</li>" for n in t["notes"]) + "</ul>")
    label = esc(t.get("source_label") or "会社の株主優待ページ")
    parts.append(f'<p class="small">{label}（<a href="{esc(t.get("source_url", ""))}" rel="noopener">出典</a>）を運営者が'
                 f' {esc(t.get("checked", ""))} に確かめてまとめた表です。有価証券報告書から読み取った上の値とは別に確かめたもので、'
                 'その後に変わっていることがあります。</p></section>')
    return "".join(parts)


def render_company_news(entries):
    items = []
    for e in entries[:3]:
        src = f'（<a href="{esc(e["source_url"])}" rel="noopener">{esc(e.get("source_label") or "会社の発表")}</a>）' if e.get("source_url") else ""
        items.append(f'<li><time datetime="{esc(e["date"])}">{esc(jp_date(e["date"], True))}</time> '
                     f'<strong>{esc(e["kind"])}</strong>：{esc(e["title"])}{src}</li>')
    return ('<aside class="card news-note" data-pp="news" aria-label="優待のお知らせ"><p><strong>優待のお知らせ</strong>'
            '（会社の発表を運営者がまとめたもの）</p><ul>' + "".join(items) +
            '</ul><p class="small"><a href="../news/index.html">新設・変更・廃止の一覧</a></p></aside>')


def step_companies(site, cfg, ctx):
    aliases = load_json(DATA / "brand_aliases.json", {})
    tiers = load_json(DATA / "tiers.json", {})
    news_by_code = {}
    for e in ctx["news"]:
        news_by_code.setdefault(e["code"], []).append(e)
    site_url = cfg["site_url"]
    n = 0
    for rel in [r for r in ctx["html"] if r.startswith("c/")]:
        code = Path(rel).stem
        h = site.get(rel)
        m = re.search(r'<h1( data-formal="([^"]*)")?>(.*?)</h1>', h, re.S)
        if not m:
            log(f"  警告: {rel} に h1 がありません")
            continue
        if m.group(2) is not None:
            formal = strip_tags(m.group(2))
        else:
            formal = re.sub(r"（" + re.escape(code) + r"）$", "", strip_tags(m.group(3)))
        short = shorten_company_name(formal)
        alias = aliases.get(code)
        if alias and alias in short:
            alias = None
        label = f"{short}（{alias}・{code}）" if alias else f"{short}（{code}）"
        ctx["names"][code] = short

        # 要点の値
        items = dl_value(h, "もらえる品")
        shares = dl_value(h, "必要株数（最小の段）")
        hold = dl_value(h, "継続保有")
        amount = dl_value(h, "年額の推定")
        corp = dl_value(h, "企業情報")
        market, _, sector = corp.partition(" / ")
        mm = re.search(r"（権利月：(.*?)）</dd>", h, re.S)
        months = strip_tags(mm.group(1)) if mm else ""
        mk = re.search(r'<dl class="summary market">(.*?)</dl>', h, re.S)
        yld = dl_value(mk.group(1), "優待利回り") if mk else ""
        md = re.search(r"株価から計算した値（(\d{4}-\d{2}-\d{2}) の終値）", h)
        ydate = md.group(1) if md else ""
        t = tiers.get(code)
        tier_text = ""
        if t and t.get("tiers"):
            first = t["tiers"][0]
            tier_text = f"{first.get('shares', '')}で{first.get('content', '')}"

        # C-2 題・見出し・説明文
        title = f"{label}の株主優待｜内容・権利確定日・必要株数"
        h = set_all_titles(h, esc(title) + SUFFIX)
        h = set_h1(h, esc(label) + "の株主優待", f' data-formal="{esc(formal)}"')
        desc = company_description(short, code, items, months, shares, hold, amount, yld, ydate, tier_text)
        h = set_all_descriptions(h, esc(desc))

        def crumb(mc):
            head, sep, _last = mc.group(2).rpartition(" ＞ ")
            return mc.group(1) + head + sep + esc(f"{short}（{code}）の株主優待") + mc.group(3)
        h = re.sub(r'(<nav class="crumbs"[^>]*>)(.*?)(</nav>)', crumb, h, count=1, flags=re.S)
        crumb_name = json.dumps(f"{short}（{code}）の株主優待", ensure_ascii=False)
        h = re.sub(r'("name":)"[^"]*"(,"item":"' + re.escape(f"{site_url}/c/{code}.html") + '")',
                   lambda mc: mc.group(1) + crumb_name + mc.group(2), h)
        h = re.sub(r'data-share-text="[^"]*"', lambda _m: f'data-share-text="{esc(label)}の株主優待"', h)
        if "<dt>社名</dt>" not in h:
            h = re.sub(r'(<dl class="facts">)(\s*<dt>企業情報</dt>)',
                       lambda mc: mc.group(1) + f"<dt>社名</dt><dd>{esc(formal)}</dd>" + mc.group(2), h, count=1)

        # C-5 定型文
        for rx, rep in BOILERPLATE:
            h = rx.sub(rep, h)

        # C-6 株数ごとの優待内容
        h = re.sub(r'<section class="card tiers"[^>]*data-pp="tiers">.*?</section>', "", h, flags=re.S)
        if t and t.get("tiers") and t.get("source_url") and t.get("checked"):
            block = render_tiers(t)
            if "<h2>優待利回りの計算</h2>" in h:
                h = h.replace("<h2>優待利回りの計算</h2>", block + "\n<h2>優待利回りの計算</h2>", 1)
            else:
                h = h.replace("<h2>出典と加工</h2>", block + "\n<h2>出典と加工</h2>", 1)

        # C-9 この会社のお知らせ
        h = re.sub(r'<aside class="card news-note" data-pp="news".*?</aside>\n?', "", h, flags=re.S)
        if code in news_by_code:
            h = h.replace('<dl class="summary">', render_company_news(news_by_code[code]) + '\n<dl class="summary">', 1)

        # C-12 まとめて購読
        if "webcal://" not in h:
            h = re.sub(r'(<p class="small cal-link">.*?)(</p>)',
                       lambda mc: mc.group(1) + f'・<a href="{WEBCAL}">すべての月をまとめて購読</a>' + mc.group(2),
                       h, count=1, flags=re.S)

        site.put(rel, h)
        n += 1
        photo = ROOT / "assets" / "benefits" / f"{code}-01.webp"
        ctx["og_cards"][code] = {
            "label": f"{short}（{alias}）" if alias else short, "code": code, "market": market, "sector": sector,
            "months": months, "shares": shares, "items": items.replace(" / ", "、"), "hold": hold,
            "photo": str(photo) if photo.exists() else None,
        }
    log(f"  会社ページ: {n} ページ")


# ---------------------------------------------------------------------------
# C-3 月のページの年 / C-4 題 / C-8 noindex
# ---------------------------------------------------------------------------
MONTH_PAGE = re.compile(r"^(list/month-(\d{2})(-[a-z0-9-]+)?|list/item-quo-(\d{2})|rank/month-(\d{2}))\.html$")

PHRASES = {
    "100株以下・長期保有の条件の記載がない株主優待": "初心者向けの株主優待（100株以下・長期保有の条件の記載なし）",
    "特典欄に「新設」の語がある会社": "株主優待の新設（特典欄に「新設」の記載がある会社）",
    "特典欄に「拡充」の語がある会社": "株主優待の拡充（特典欄に「拡充」の記載がある会社）",
    "特典欄に「変更」の語がある会社": "株主優待の変更（特典欄に「変更」の記載がある会社）",
    "特典欄に「廃止」の語がある会社": "株主優待の廃止（特典欄に「廃止」の記載がある会社）",
}

NOINDEX_PAGES = ["list/category-unknown.html"]


def step_titles(site, ctx):
    build = ctx["build_date"]
    mapping = {}
    for rel in ctx["html"]:
        m = MONTH_PAGE.match(rel)
        if not m:
            continue
        month = int(m.group(2) or m.group(4) or m.group(5))
        year = build.year if month >= build.month else build.year + 1
        t = get_title(site.get(rel))
        nt = re.sub(r"【\d{4}年】", f"【{year}年】", t) if re.search(r"【\d{4}年】", t) else t + f"【{year}年】"
        if nt != t:
            mapping[t] = nt
    n1 = global_replace(site, mapping, ctx["html"])
    n2 = global_replace(site, PHRASES, ctx["html"])
    log(f"  月のページの年: {len(mapping)} 件の題（{n1} ファイル）、題の言い換え: {n2} ファイル")

    y = build.year
    for rel, title, h1, lead in [
        ("list/index.html", "株主優待を条件で探す｜権利月・必要株数・優待の種類・金額", "株主優待を条件で探す", "株主優待を条件で探す。"),
        ("rank/index.html", f"株主優待ランキング【{y}年】優待利回り・最低投資額・年額", "株主優待ランキング", "株主優待ランキング。"),
    ]:
        if not site.exists(rel):
            continue
        h = site.get(rel)
        h = set_all_titles(h, esc(title) + SUFFIX)
        h = set_h1(h, esc(h1))
        d = get_meta(h, "name", "description") or ""
        if not d.startswith(lead):
            h = set_all_descriptions(h, esc(lead) + d)
        site.put(rel, h)

    for rel in NOINDEX_PAGES:
        if site.exists(rel):
            h = site.get(rel)
            if '<meta name="robots"' not in h:
                h = insert_after_viewport(h, '<meta name="robots" content="noindex">')
            else:
                h = re.sub(r'<meta name="robots" content="[^"]*">', '<meta name="robots" content="noindex">', h, count=1)
            site.put(rel, h)


def step_method(site):
    rel = "method.html"
    if not site.exists(rel):
        return
    h = site.get(rel)
    h = h.replace("<h2>項目の意味</h2>", '<h2 id="terms">項目の意味</h2>', 1)
    h = re.sub(r'<h2 id="read-company">.*?</ul>\n', "", h, flags=re.S)
    if '<h2 id="market">' in h:
        h = h.replace('<h2 id="market">', METHOD_SECTION + '<h2 id="market">', 1)
    site.put(rel, h)


# ---------------------------------------------------------------------------
# C-9 新設・変更・廃止
# ---------------------------------------------------------------------------
def page_from_template(site, cfg, template_rel, rel, title, desc, crumbs, main_html, noindex, extra_head=""):
    """同じ深さのページを型にして、新しいページを作る（見出しの帯とフッターは型のまま）。"""
    h = site.get(template_rel)
    site_url = cfg["site_url"]
    url = url_for(rel, site_url)
    full = esc(title) + SUFFIX
    h = set_all_titles(h, full)
    h = set_all_descriptions(h, esc(desc))
    h = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{url}">', h, count=1)
    h = set_meta(h, "property", "og:url", url)
    h = re.sub(r'<meta name="robots" content="[^"]*">\n?', "", h)
    h = insert_after_viewport(h, '<meta name="robots" content="noindex">' if noindex else '<meta name="robots" content="max-image-preview:large">')
    bl = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": nm, "item": u} for i, (nm, u) in enumerate(crumbs)]}
    bl_json = json.dumps(bl, ensure_ascii=False, separators=(",", ":"))
    h = re.sub(r'<script type="application/ld\+json">\{"@context":"https://schema.org","@type":"(BreadcrumbList|Article|TechArticle|FAQPage)".*?</script>',
               "", h, flags=re.S)
    h = h.replace("</head>", f'<script type="application/ld+json">{bl_json}</script>{extra_head}\n</head>', 1)
    h = re.sub(r'<main id="main" class="wrap">.*?</main>', lambda _m: main_html, h, count=1, flags=re.S)
    site.put(rel, h)


def step_news(site, cfg, ctx):
    entries = ctx["news"]
    site_url = cfg["site_url"]
    min_n = int(cfg.get("news_min_entries_to_index", 3))
    noindex = len(entries) < min_n
    ctx["news_noindex"] = noindex
    names = ctx["names"]
    year = ctx["build_date"].year

    groups = {}
    for e in entries:
        groups.setdefault(e["date"][:7], []).append(e)
    body = []
    if entries:
        for ym in sorted(groups, reverse=True):
            y, mth = ym.split("-")
            body.append(f"<h2>{int(y)}年{int(mth)}月</h2><ul class=\"news-list\">")
            for e in groups[ym]:
                name = names.get(e["code"], e.get("name", ""))
                company = f'<a href="../c/{esc(e["code"])}.html">{esc(name)}（{esc(e["code"])}）</a>' if (ROOT / f'c/{e["code"]}.html').exists() else f'{esc(e.get("name", ""))}（{esc(e["code"])}）'
                summary = f'。{esc(e["summary"])}' if e.get("summary") else ""
                src = f'（<a href="{esc(e["source_url"])}" rel="noopener">{esc(e.get("source_label") or "会社の発表")}</a>）' if e.get("source_url") else ""
                body.append(f'<li><time datetime="{esc(e["date"])}">{esc(jp_date(e["date"]))}</time> '
                            f'<span class="chip news-kind">{esc(e["kind"])}</span> {company}：{esc(e["title"])}{summary}{src}</li>')
            body.append("</ul>")
    else:
        body.append("<p>まだ載せているお知らせはありません。会社の発表を確かめたものから順に載せます。</p>")

    main = ('<main id="main" class="wrap">\n'
            '<nav class="crumbs" aria-label="現在地"><a href="../index.html">トップ</a> ＞ 株主優待の新設・変更・廃止</nav>\n'
            f'<h1>株主優待の新設・変更・廃止のお知らせ【{year}年】</h1>\n'
            '<div class="lead"><p>会社が発表した株主優待の新設・拡充・変更・廃止を、発表日の新しい順に載せています。'
            '会社の発表（適時開示など）を運営者が確かめてまとめたものです。正式な内容は、各行の出典の発表をご覧ください。</p></div>\n'
            '<p class="small"><a href="feed.xml">RSS で受け取る</a>（新しいお知らせを、RSS リーダーで受け取れます）</p>\n'
            + "\n".join(body) +
            '\n<h2>有価証券報告書の特典欄の語から</h2>\n'
            '<p class="small">こちらは会社の発表ではなく、有価証券報告書の特典欄にある語から規則で付けた印です。実際に変わったことを示すものではありません。</p>\n'
            '<ul class="links"><li><a href="../list/change-new.html">特典欄に「新設」の記載がある会社</a></li>'
            '<li><a href="../list/change-expand.html">特典欄に「拡充」の記載がある会社</a></li>'
            '<li><a href="../list/change-change.html">特典欄に「変更」の記載がある会社</a></li>'
            '<li><a href="../list/change-end.html">特典欄に「廃止」の記載がある会社</a></li></ul>\n'
            '</main>')
    desc = (f"株主優待の新設・変更・廃止のお知らせ【{year}年】。会社が発表した株主優待の新設・拡充・変更・廃止を、"
            "発表日の新しい順にまとめた一覧です。出典の発表へのリンクつき。")
    feed_link = f'<link rel="alternate" type="application/rss+xml" title="優待しらべ 株主優待の新設・変更・廃止" href="{site_url}/news/feed.xml">'
    page_from_template(site, cfg, "guide/rights-last-day.html", "news/index.html",
                       f"株主優待の新設・変更・廃止のお知らせ【{year}年】", desc,
                       [("トップ", site_url + "/"), ("株主優待の新設・変更・廃止", site_url + "/news/index.html")],
                       main, noindex, extra_head=feed_link)

    # RSS
    def rfc822(d):
        dt = datetime.datetime.combine(datetime.date.fromisoformat(d), datetime.time(9, 0), JST)
        return format_datetime(dt)
    items = []
    for e in entries[:50]:
        name = names.get(e["code"], e.get("name", ""))
        link = f'{site_url}/c/{e["code"]}.html' if (ROOT / f'c/{e["code"]}.html').exists() else f"{site_url}/news/index.html"
        desc_i = (e.get("summary") or e["title"]) + (f' 出典: {e["source_url"]}' if e.get("source_url") else "")
        items.append(f'<item><title>{esc("【" + e["kind"] + "】" + name + "（" + e["code"] + "）：" + e["title"])}</title>'
                     f'<link>{esc(link)}</link><guid isPermaLink="false">yutai-news-{esc(e["date"])}-{esc(e["code"])}-{esc(e["kind"])}</guid>'
                     f'<pubDate>{rfc822(e["date"])}</pubDate><description>{esc(desc_i)}</description></item>')
    last = rfc822(entries[0]["date"]) if entries else rfc822(ctx["build_date"].isoformat())
    feed = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            '<title>優待しらべ｜株主優待の新設・変更・廃止</title>'
            f'<link>{site_url}/news/index.html</link>'
            '<description>会社が発表した株主優待の新設・拡充・変更・廃止を、運営者が確かめてまとめたお知らせです。</description>'
            '<language>ja</language>'
            f'<atom:link href="{site_url}/news/feed.xml" rel="self" type="application/rss+xml"/>'
            f'<lastBuildDate>{last}</lastBuildDate>' + "".join(items) + "</channel></rss>\n")
    site.put("news/feed.xml", feed)

    # 見出しの帯のリンク（お知らせが1件以上あるときだけ）
    show = bool(entries)
    rx_nav = re.compile(r'<a href="(?:\.\./)*news/index\.html">新設・廃止</a>')
    for rel in ctx["html"] + ["news/index.html"]:
        h = site.get(rel)
        nh = rx_nav.sub("", h)
        if show:
            pre = prefix_for(rel)
            nh = re.sub(r'(<nav class="site-nav"[^>]*>.*?<a href="(?:\.\./)*calendar/index\.html">カレンダー</a>)',
                        lambda mc: mc.group(1) + f'<a href="{pre}news/index.html">新設・廃止</a>', nh, count=1, flags=re.S)
        if rel == "index.html":
            nh = re.sub(r'<link rel="alternate" type="application/rss\+xml"[^>]*>\n?', "", nh)
            if show:
                nh = nh.replace("</head>", feed_link + "\n</head>", 1)
        if nh != h:
            site.put(rel, nh)
    if site.exists("list/index.html"):
        h = site.get("list/index.html")
        h = re.sub(r'<p data-pp="news-link">.*?</p>', "", h)
        if show:
            h = h.replace("<h2>優待の変化</h2>", '<h2>優待の変化</h2><p data-pp="news-link"><a href="../news/index.html">'
                          '会社が発表した新設・変更・廃止のお知らせ（運営者が確かめたもの）</a></p>', 1)
        site.put("list/index.html", h)
    log(f"  お知らせ: {len(entries)} 件（{'noindex' if noindex else '検索に出す'}）")


# ---------------------------------------------------------------------------
# C-12 カレンダーの購読
# ---------------------------------------------------------------------------
def step_calendar(site, ctx):
    gcal = "https://calendar.google.com/calendar/r?cid=" + urllib.parse.quote(WEBCAL, safe="")
    box = ('<section class="card subscribe" data-pp="subscribe"><h2>カレンダーを購読する</h2>'
           '<p>権利付き最終日を、お使いのカレンダーに入れられます。購読すると、データの更新に合わせて予定も自動で増えます'
           '（月ごとに .ics を取り込み直す必要はありません）。</p>'
           f'<p class="subscribe-links"><a class="btn-link" href="{WEBCAL}">iPhone・Mac のカレンダーで購読</a>'
           f'<a class="btn-link" href="{esc(gcal)}" rel="noopener">Google カレンダーで購読</a></p>'
           '<p class="small">うまく開けないときは、カレンダーのアプリで「URL で追加」を選び、'
           '<code>https://yutai-shirabe.com/calendar/yutai.ics</code> を入れてください。予定は権利付き最終日ごとに1件（終日）で、'
           'その日の会社の一覧ページへのリンクが入ります。</p></section>')
    rel = "calendar/index.html"
    if site.exists(rel):
        h = site.get(rel)
        h = re.sub(r'<section class="card subscribe" data-pp="subscribe">.*?</section>\n?', "", h, flags=re.S)
        if re.search(r'<p><a href="yutai\.ics">[^<]*</a>[^<]*</p>', h):
            # 「次の12ヶ月分をまとめてカレンダーに追加」の下（月の表のすぐ後）
            h = re.sub(r'(<p><a href="yutai\.ics">[^<]*</a>[^<]*</p>)', lambda m: m.group(1) + box, h, count=1)
        else:
            h = re.sub(r"(<h1>.*?</h1>)", lambda m: m.group(1) + "\n" + box, h, count=1, flags=re.S)
        site.put(rel, h)
    for r in ctx["html"]:
        if re.match(r"^calendar/\d{4}-\d{2}\.html$", r):
            h = site.get(r)
            if "webcal://" not in h:
                h = re.sub(r'(<p><a href="yutai-\d{4}-\d{2}\.ics">カレンダーに追加</a>（[^<]*）)(</p>)',
                           lambda m: m.group(1) + f'・<a href="{WEBCAL}">すべての月をまとめて購読</a>' + m.group(2), h, count=1)
                site.put(r, h)
    ics = "calendar/yutai.ics"
    if site.exists(ics):
        t = site.get(ics)
        nl = "\r\n" if "\r\n" in t else "\n"
        if "REFRESH-INTERVAL" not in t:
            t = re.sub(r"(X-WR-CALNAME:[^\r\n]*\r?\n)",
                       lambda m: m.group(1) + "X-WR-CALDESC:株主優待の権利付き最終日（優待しらべ）" + nl
                       + "REFRESH-INTERVAL;VALUE=DURATION:P1D" + nl + "X-PUBLISHED-TTL:P1D" + nl, t, count=1)
            site.put(ics, t)


# ---------------------------------------------------------------------------
# C-1 / C-10 / C-11 head の共通部品
# ---------------------------------------------------------------------------
def step_head(site, cfg, ctx, og_paths):
    site_url = cfg["site_url"]
    same_as = [u for u in [cfg.get("note_url"), cfg.get("x_url")] if u]
    for rel in ctx["html"] + ["news/index.html"]:
        h = site.get(rel)
        # 大きな画像のプレビューを許す（noindex のページは触らない）
        if '<meta name="robots"' not in h:
            h = insert_after_viewport(h, '<meta name="robots" content="max-image-preview:large">')
        # 運営者の JSON-LD に sameAs（note・X）

        def person(m):
            try:
                obj = json.loads(m.group(2))
            except ValueError:
                return m.group(0)
            if same_as:
                obj["sameAs"] = same_as
            else:
                obj.pop("sameAs", None)
            return m.group(1) + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + m.group(3)
        h = re.sub(r'(<script type="application/ld\+json">)(\{"@context":"https://schema.org","@type":"Person".*?\})(</script>)', person, h, count=1)
        # C-11 会社ごとの共有用画像
        if rel.startswith("c/"):
            code = Path(rel).stem
            if code in og_paths:
                img = f"{site_url}/{og_paths[code]}"
                h = set_meta(h, "property", "og:image", img)
                h = set_meta(h, "name", "twitter:image", img)
        site.put(rel, h)

    # Search Console・Bing の所有確認（設定にあるときだけ）
    h = site.get("index.html")
    for name, key in [("google-site-verification", "google_site_verification"), ("msvalidate.01", "bing_site_verification")]:
        h = re.sub(r'<meta name="%s" content="[^"]*">\n?' % re.escape(name), "", h)
        if cfg.get(key):
            h = insert_after_viewport(h, f'<meta name="{name}" content="{esc(cfg[key])}">')
    site.put("index.html", h)

    # 運営者情報に X
    if site.exists("operator.html"):
        h = site.get("operator.html")
        h = re.sub(r'<br data-pp="x">X：<a [^>]*>[^<]*</a>', "", h)
        if cfg.get("x_url"):
            x = esc(cfg["x_url"])
            h = re.sub(r'(<dt>関連するページ</dt><dd>.*?)(</dd>)',
                       lambda m: m.group(1) + f'<br data-pp="x">X：<a href="{x}" rel="noopener">{x}</a>' + m.group(2), h, count=1, flags=re.S)
        site.put("operator.html", h)


CSS_BLOCK = """/* pp:start 改善案12（tools/postprocess.py が足す部分。手で直さないでください） */
.tiers h2{margin-top:0}
.tiers .facts{margin-bottom:8px}
.subscribe h2{margin-top:0}
.subscribe-links{display:flex;flex-wrap:wrap;gap:8px}
.btn-link{display:inline-block;padding:8px 16px;border:1px solid var(--primary);border-radius:8px;background:var(--surface);color:var(--primary);text-decoration:none;font-weight:600}
.btn-link:hover{background:var(--primary-weak)}
.news-note{background:var(--accent-weak);border-color:#f0d2bf}
.news-note ul{margin:4px 0;padding-left:1.2em}
.news-list{list-style:none;padding:0}
.news-list li{padding:10px 0;border-bottom:1px solid var(--border)}
.news-kind{margin:0 4px}
/* pp:end */
"""


def step_css(site):
    rel = "assets/site.css"
    t = site.get(rel)
    t = re.sub(r"/\* pp:start.*?/\* pp:end \*/\n?", "", t, flags=re.S)
    if not t.endswith("\n"):
        t += "\n"
    site.put(rel, t + CSS_BLOCK)


# ---------------------------------------------------------------------------
# C-7 サイトマップの lastmod を中身の変わった日に
# ---------------------------------------------------------------------------
def content_key(h):
    """lastmod を決めるための中身（題・説明文・本文）。見出しの帯・フッター（作成日）・head の部品は含めない。"""
    t = get_title(h)
    d = get_meta(h, "name", "description") or ""
    m = re.search(r"<main.*?</main>", h, re.S)
    body = m.group(0) if m else h
    body = re.sub(r"\s+", " ", body)
    return sha(t + "\n" + d + "\n" + body)


class GitBlobs:
    def __init__(self):
        self.proc = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def read(self, rev, rel):
        self.proc.stdin.write(f"{rev}:{rel}\n".encode())
        self.proc.stdin.flush()
        header = self.proc.stdout.readline().decode()
        if header.endswith("missing\n"):
            return None
        size = int(header.split()[2])
        data = self.proc.stdout.read(size)
        self.proc.stdout.read(1)
        return data.decode("utf-8", "replace")

    def close(self):
        self.proc.stdin.close()
        self.proc.wait()


def git_last_change(rel, blobs, current_key):
    """git の履歴から、中身（content_key）が最後に変わったコミットの日（JST）を返す。"""
    try:
        out = subprocess.run(["git", "log", "--format=%H %cd", "--date=format-local:%Y-%m-%d", "--", rel],
                             cwd=ROOT, capture_output=True, text=True, env={**os.environ, "TZ": "Asia/Tokyo"}).stdout
    except OSError:
        return None
    revs = [ln.split() for ln in out.splitlines() if ln.strip()]
    last_date = None
    key = current_key
    for rev, date in revs:
        text = blobs.read(rev, rel)
        if text is None:
            break
        k = content_key(text)
        if k != key:
            break
        last_date = date
    return last_date


def step_sitemap(site, cfg, ctx):
    site_url = cfg["site_url"]
    sm = site.get("sitemap.xml")
    entries = re.findall(r"<url><loc>([^<]*)</loc>(?:<lastmod>([^<]*)</lastmod>)?</url>", sm)
    gen = {}
    order = []
    for loc, lm in entries:
        rel = "index.html" if loc == site_url + "/" else loc[len(site_url) + 1:]
        gen[rel] = lm
        order.append(rel)
    if "news/index.html" not in order:
        order.append("news/index.html")
    state_path = STATE / "lastmod.json"
    state = load_json(state_path, {})
    today = today_jst().isoformat()
    blobs = None
    out, new_state = [], {}
    for rel in order:
        if not site.exists(rel):
            continue
        h = site.get(rel)
        if is_noindex(h):
            continue
        key = content_key(h)
        prev = state.get(rel)
        if prev and prev.get("h") == key:
            d = prev["d"]
        elif prev:
            d = today
        else:
            head = None
            try:
                head = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")
            except OSError:
                pass
            if head and content_key(head) == key:
                if blobs is None:
                    blobs = GitBlobs()
                d = git_last_change(rel, blobs, key) or gen.get(rel) or today
            else:
                d = today
        if gen.get(rel) and gen[rel] > d:
            d = gen[rel]
        new_state[rel] = {"h": key, "d": d}
        out.append(f"<url><loc>{url_for(rel, site_url)}</loc><lastmod>{d}</lastmod></url>")
    if blobs:
        blobs.close()
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(out) + "\n</urlset>\n")
    site.put("sitemap.xml", xml)
    ctx["lastmod_state"] = new_state
    log(f"  サイトマップ: {len(out)} URL")


# ---------------------------------------------------------------------------
def build_date_of(site):
    m = re.search(r"このサイトの作成日: (\d{4}-\d{2}-\d{2})", site.get("index.html"))
    return datetime.date.fromisoformat(m.group(1)) if m else today_jst()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-og", action="store_true", help="共有用画像（OG 画像）を作らない")
    ap.add_argument("--check", action="store_true", help="書き込まずに、変わるファイルの数だけ出す")
    args = ap.parse_args()

    cfg = config()
    cfg.setdefault("site_url", "https://yutai-shirabe.com")
    site = Site()
    news = load_json(DATA / "news.json", [])
    news = sorted(news, key=lambda e: (e["date"], e["code"]), reverse=True)
    ctx = {"html": html_files(), "names": {}, "og_cards": {}, "news": news, "build_date": build_date_of(site)}
    ctx["html"] = [r for r in ctx["html"] if r != "news/index.html"]
    log(f"後処理（作成日 {ctx['build_date']}・HTML {len(ctx['html'])} ファイル）")

    step_companies(site, cfg, ctx)
    step_titles(site, ctx)
    step_method(site)
    step_news(site, cfg, ctx)
    step_calendar(site, ctx)
    og_paths = {}
    if not args.no_og and not args.check:
        import og_images
        og_paths = og_images.build_all(ctx["og_cards"], cfg, log)
    else:
        prev = load_json(STATE / "og.json", {})
        og_paths = {c: v["path"] for c, v in prev.items() if (ROOT / v["path"]).exists()}
    step_head(site, cfg, ctx, og_paths)
    step_css(site)
    step_sitemap(site, cfg, ctx)

    # C-1 IndexNow の鍵のファイル
    key = cfg.get("indexnow_key")
    if key:
        site.put(f"{key}.txt", key)

    changed = site.changed()
    if args.check:
        log(f"変わるファイル: {len(changed)}")
        for r in changed[:20]:
            log("  " + r)
        return
    n = site.flush()
    save_json(STATE / "lastmod.json", ctx["lastmod_state"])
    log(f"書き込んだファイル: {n}")


if __name__ == "__main__":
    main()
