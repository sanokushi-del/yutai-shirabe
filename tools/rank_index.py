"""ランキングの目次（rank/index.html）を、各ランキングの上位3社を見せるカードの形にする。

中身は各ランキングのページ（rank/*.html）の表と「計算の決め方」から読むので、
サイトを作り直したあとも、後処理を何度かけても同じ結果になる。postprocess.py の step_rank_index から使う。
"""
import re

from pplib import esc, jp_date, shorten_company_name, strip_tags

TOP_N = 3

# 節（h2）の順。pages に無いランキングのページは、month-NN なら「権利月ごと」、それ以外は「条件で絞る」へ入れる
SECTIONS = [
    {"id": "yield", "pill": "利回り", "title": "利回りのランキング",
     "desc": "優待・配当の1年分が、株価に比べてどれだけ大きいかの順です。",
     "pages": ["yutai-yield", "total-yield", "dividend-yield"], "kind": "box"},
    {"id": "money", "pill": "投資額・優待の金額", "title": "最低投資額・優待の金額のランキング",
     "desc": "優待を受けられる最小の金額が少ない順と、優待の1年分の金額（推定）が多い順です。",
     "pages": ["min-invest", "amount"], "kind": "box"},
    {"id": "ratio", "pill": "PER・PBR", "title": "PER・PBR のランキング",
     "desc": "株価を、1株あたりの予想利益（PER）や純資産（PBR）と比べた値の低い順です。",
     "pages": ["per", "pbr"], "kind": "box"},
    {"id": "month", "pill": "権利月ごと", "title": "権利月ごとのランキング（優待利回りの高い順）",
     "desc": "その月に権利確定日がある会社を、優待利回りの高い順に並べています。近い月から順に出しています。",
     "pages": [], "kind": "tile"},
    {"id": "filter", "pill": "条件で絞る", "title": "品目・最低投資額で絞ったランキング（優待利回りの高い順）",
     "desc": "QUOカードがもらえる会社や、少ない資金で買える会社に絞り、優待利回りの高い順に並べています。",
     "pages": [], "kind": "tile"},
]

# カードに出す短い名前・式・単位の印
LABEL = {"yutai-yield": "優待利回り", "total-yield": "総合利回り", "dividend-yield": "配当利回り",
         "min-invest": "最低投資額", "amount": "優待の年額", "per": "PER", "pbr": "PBR"}
FORMULA = {"yutai-yield": "優待の年額の推定 ÷ 最低投資額",
           "total-yield": "優待利回り ＋ 配当利回り",
           "dividend-yield": "予想年間配当 ÷ 株価",
           "min-invest": "株価 × 優待を受けられる最小の株数",
           "amount": "1回の金額 × 年の回数（株価は使いません）",
           "per": "株価 ÷ 1株あたりの予想利益",
           "pbr": "株価 ÷ 1株あたり純資産"}
BADGE = {"%": "%", "円": "円", "倍": "倍"}

NOTES = [
    "株価が低い会社は、同じ優待でも利回りが大きく出ます。上位の値がとても大きいときは、会社ページで株価と優待の内容を確かめてください。",
    "同じ値の会社はコード順に並べ、値を出せない会社は載せていません。各ランキングに載せるのは上位100社です。",
    "優待の年額の推定を使うランキング（優待利回り・総合利回り・優待の年額）では、年額の推定が割引券・値引きの額と読めた会社を載せていません。除いた社数は、各ランキングに書いています。",
    "権利月・品目・最低投資額で絞ったランキングは、優待利回りを出せる会社が30社以上あるものだけ作っています。",
    "優待の必要株数・年額の推定は、有価証券報告書の特典欄から規則で読み取った推定を含みます。",
    "終値そのものは載せていません。載せているのは、各ランキングの式で計算した値です。",
]


def _cells(tr):
    out = {}
    for attrs, inner in re.findall(r"<td([^>]*)>(.*?)</td>", tr, re.S):
        m = re.search(r'data-label="([^"]+)"', attrs)
        if m:
            out[m.group(1)] = inner
    return out


def parse_rank_page(h):
    """ランキングのページから、題・式・社数・上位の行を取り出す。表が無ければ None。"""
    ths = [strip_tags(t) for t in re.findall(r'<th scope="col"[^>]*>(.*?)</th>', h, re.S)]
    body = re.search(r"<tbody>(.*?)</tbody>", h, re.S)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S)
    if len(ths) < 4 or not body or not h1:
        return None
    metric = ths[3]
    trs = re.findall(r"<tr>(.*?)</tr>", body.group(1), re.S)
    rows = []
    for tr in trs[:TOP_N]:
        c = _cells(tr)
        link = re.search(r'<a href="([^"]+)">(.*?)</a>', c.get("会社名", ""), re.S)
        if not link:
            continue
        chip = c.get("主な種類", "").strip()
        rows.append({
            "href": link.group(1),
            "name": shorten_company_name(strip_tags(link.group(2))),
            "code": strip_tags(c.get("コード", "")),
            "value": strip_tags(c.get(metric, "")),
            "shares": strip_tags(c.get("必要株数", "")),
            "amount": strip_tags(c.get("年額の推定", "")) if metric != "年額の推定" else "",
            "chip": chip if chip.startswith("<span") else "",
            "months": strip_tags(c.get("権利月", "")),
        })

    def dd(label):
        m = re.search(r"<dt>" + re.escape(label) + r"</dt>\s*<dd>(.*?)</dd>", h, re.S)
        return strip_tags(m.group(1)) if m else ""

    out_text = dd("対象外の会社")
    ranked = re.search(r"残りの([\d,]+)社", out_text)
    listed = re.search(r"掲載している([\d,]+)社", out_text)
    base = re.match(r"\d{4}-\d{2}-\d{2}", dd("基準の日"))
    title = strip_tags(h1.group(1))
    title = re.sub(r"\s*(?:[\d,]+社)?\s*【\d{4}年】\s*$", "", title)
    title = re.sub(r"\s*[\d,]+社\s*$", "", title)
    return {"title": title, "metric": metric, "formula": dd("計算の決め方"), "rows": rows,
            "shown": len(trs), "ranked": ranked.group(1) if ranked else "",
            "listed": listed.group(1) if listed else "", "base": base.group(0) if base else ""}


def _value_html(v):
    m = re.match(r"^([\d,.\-]+)(\D*)$", v)
    if not m:
        return esc(v)
    return f'{esc(m.group(1))}<small>{esc(m.group(2))}</small>' if m.group(2) else esc(m.group(1))


def _more(slug, info):
    shown, ranked = info["shown"], info["ranked"]
    if ranked and ranked.replace(",", "") == str(shown):
        txt = f"{shown}社すべてを見る"
    elif ranked:
        txt = f"上位{shown}社を見る<span class=\"rk-more-sub\">（{esc(ranked)}社から）</span>"
    else:
        txt = f"上位{shown}社を見る"
    return f'<a class="rk-more" href="{slug}.html">{txt} →</a>'


def _badge(slug, info):
    rows = info["rows"]
    unit = re.sub(r"[\d,.\-]", "", rows[0]["value"]) if rows else ""
    return BADGE.get(unit, "#")


def render_box(slug, info):
    label = LABEL.get(slug, info["metric"])
    formula = FORMULA.get(slug) or info["formula"].split("。")[0]
    lis = []
    for i, r in enumerate(info["rows"], 1):
        sub = []
        if r["chip"]:
            sub.append(r["chip"])
        if re.match(r"\d", r["shares"]):
            sub.append(f"<span>{esc(r['shares'])}</span>")
        if re.match(r"\d", r["amount"]):
            sub.append(f"<span>年{esc(r['amount'])}</span>")
        if re.match(r"\d", r["months"]):
            sub.append(f"<span>権利月 {esc(r['months'])}</span>")
        lis.append(f'<li><span class="rk-no">{i}</span><a class="rk-co" href="{esc(r["href"])}">{esc(r["name"])}</a>'
                   f'<span class="rk-val">{_value_html(r["value"])}</span>'
                   + (f'<span class="rk-sub">{"".join(sub)}</span>' if sub else "") + "</li>")
    return (f'<article class="rk-box">'
            f'<h3 class="rk-box-title"><a href="{slug}.html"><span class="rank-badge" aria-hidden="true">{_badge(slug, info)}</span>'
            f'<span class="rk-box-name">{esc(info["title"])}</span></a></h3>'
            f'<p class="rk-formula"><span class="rk-key">{esc(label)}</span> = {esc(formula)}</p>'
            f'<ol class="rk-list">{"".join(lis)}</ol>{_more(slug, info)}</article>')


def render_tile(slug, info):
    m = re.match(r"month-(\d{2})$", slug)
    if m:
        head = f'<span class="rk-big">{int(m.group(1))}月</span>に権利確定日がある株主優待'
    else:
        t = re.sub(r"\s*優待利回りの高い順$", "", info["title"])
        head = esc(t)
    lis = [f'<li><span class="rk-no">{i}</span><a href="{esc(r["href"])}">{esc(r["name"])}</a>'
           f'<span class="rk-val">{_value_html(r["value"])}</span></li>' for i, r in enumerate(info["rows"], 1)]
    return (f'<article class="rk-tile"><h3 class="rk-tile-title"><a href="{slug}.html">{head}</a></h3>'
            f'<ol class="rk-mini">{"".join(lis)}</ol>{_more(slug, info)}</article>')


def build_main(pages, build_date):
    """pages: {slug: parse_rank_page の結果}。rank/index.html の <main> の中身を返す。"""
    groups = {s["id"]: [] for s in SECTIONS}
    placed = set()
    for s in SECTIONS:
        for slug in s["pages"]:
            if slug in pages:
                groups[s["id"]].append(slug)
                placed.add(slug)
    rest = sorted(p for p in pages if p not in placed)
    months = [p for p in rest if re.match(r"month-\d{2}$", p)]
    # 近い月から（作成日の月を含めて先に、そのあと翌年の月）
    months.sort(key=lambda p: (int(p[-2:]) < build_date.month, int(p[-2:])))
    groups["month"] = months
    order = ["item-quo-yield", "invest-50k", "invest-100k"]
    groups["filter"] = sorted((p for p in rest if p not in months),
                              key=lambda p: (order.index(p) if p in order else len(order), p))

    any_info = next((pages[p] for p in ["yutai-yield"] + sorted(pages) if p in pages and pages[p]["listed"]), None)
    listed = any_info["listed"] if any_info else ""
    base = next((pages[p]["base"] for p in ["yutai-yield"] + sorted(pages) if p in pages and pages[p]["base"]), "")
    base_jp = jp_date(base, with_year=True) if base else ""

    facts = []
    if base_jp:
        facts.append(f'<li><span>基準の日</span>{esc(base_jp)}の終値</li>')
    if listed:
        facts.append(f'<li><span>対象</span>{esc(listed)}社</li>')
    facts.append(f'<li><span>ランキング</span>{len(pages)}種類</li>')

    sections = [s for s in SECTIONS if groups[s["id"]]]
    pills = "".join(f'<li><a class="pill" href="#{s["id"]}">{esc(s["pill"])}</a></li>' for s in sections)
    pills += '<li><a class="pill" href="#how">計算の決め方</a></li>'

    out = ['<main id="main" class="wrap">',
           '<nav class="crumbs" aria-label="現在地"><a href="../index.html">トップ</a> ＞ ランキング</nav>',
           '<div class="hero rk-hero">',
           '<h1>株主優待ランキング</h1>',
           f'<div class="lead"><p>株主優待のある{esc(listed) + "社" if listed else "会社"}を、優待利回り・配当利回り・最低投資額・優待の年額などで並べたランキングです。'
           'ここでは各ランキングの上位3社を紹介しています。続きは各ランキングのページで、上位100社まで見られます。</p></div>',
           f'<ul class="rk-facts">{"".join(facts)}</ul>',
           f'<ul class="pills rk-jump" aria-label="このページの目次">{pills}</ul>',
           '</div>',
           '<!-- 広告の置き場所 -->',
           '<p class="small rk-caution">事実・指標の順に並べたもので、割安・割高や売買を判断するものではありません。'
           '株価が低い会社は、同じ優待でも利回りが大きく出ます。</p>']
    for s in sections:
        render = render_box if s["kind"] == "box" else render_tile
        cards = "".join(render(slug, pages[slug]) for slug in groups[s["id"]])
        out.append(f'<section class="rk-section" aria-labelledby="{s["id"]}"><h2 id="{s["id"]}">{esc(s["title"])}</h2>'
                   f'<p class="rk-desc">{esc(s["desc"])}</p>'
                   f'<div class="rk-grid{" rk-tiles" if s["kind"] == "tile" else ""}">{cards}</div></section>')

    dls = []
    for slug in ["yutai-yield", "total-yield", "dividend-yield", "min-invest", "amount", "per", "pbr"]:
        if slug in pages and pages[slug]["formula"]:
            dls.append(f'<dt>{esc(LABEL[slug])}</dt><dd>{esc(pages[slug]["formula"])}</dd>')
    notes = []
    if base:
        notes.append(f"<li>株価を使うランキングの基準の日は {esc(base)} です（この日から14日以内でいちばん新しい終値の日の終値で計算しています）。株価は日々変わります。</li>")
    notes += [f"<li>{esc(n)}</li>" for n in NOTES]
    notes.append('<li>計算の決め方は<a href="../method.html#market">作り方と限界</a>、<a href="../disclaimer.html">免責</a>に書いています。'
                 '条件を組み合わせて探すときは、<a href="../index.html#search">トップの「条件で探す」</a>を使ってください。</li>')
    out.append('<section class="rk-section rk-how" aria-labelledby="how"><h2 id="how">計算の決め方と見方</h2>'
               + (f'<dl class="facts">{"".join(dls)}</dl>' if dls else "")
               + f'<ul class="small">{"".join(notes)}</ul></section>')
    out.append("</main>")
    return "\n".join(out)


CSS = """.rk-hero .lead p{margin:0}
.rk-facts{list-style:none;margin:14px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.rk-facts li{margin:0;padding:4px 12px;background:var(--surface);border-radius:999px;box-shadow:var(--shadow);font-size:14px;font-weight:700;line-height:1.6}
.rk-facts li span{margin-right:6px;color:var(--muted);font-size:12px;font-weight:400}
.rk-jump{margin:12px 0 0}
.rk-caution{margin:10px 0 0}
.rk-section{margin-top:32px}
.rk-section>h2{margin:0 0 4px;scroll-margin-top:8px}
.rk-desc{margin:0 0 12px;color:var(--muted);font-size:14px}
.rk-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:12px}
.rk-box,.rk-tile{display:flex;flex-direction:column;min-width:0;background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);padding:14px 16px 12px}
.rk-box:hover,.rk-tile:hover{border-color:#e7c9b3}
.rk-box-title,.rk-tile-title{margin:0;font-size:16px;line-height:1.45}
.rk-box-title a{display:flex;align-items:center;gap:10px;color:var(--primary-ink);text-decoration:none}
.rk-box-title .rank-badge{flex:none}
.rk-box-title a:hover .rk-box-name,.rk-tile-title a:hover{text-decoration:underline}
.rk-tile-title a{color:var(--primary-ink);text-decoration:none}
.rk-big{font-size:26px;line-height:1.1;margin-right:2px;color:var(--accent-ink)}
.rk-formula{margin:8px 0 6px;font-size:12px;color:var(--muted)}
.rk-key{font-weight:700;color:var(--text)}
.rk-list,.rk-mini{list-style:none;margin:2px 0 10px;padding:0}
.rk-list li{display:grid;grid-template-columns:26px minmax(0,1fr) auto;column-gap:10px;row-gap:3px;align-items:center;margin:0;padding:9px 0;border-top:1px solid var(--border)}
.rk-mini li{display:grid;grid-template-columns:22px minmax(0,1fr) auto;column-gap:8px;align-items:center;margin:0;padding:6px 0;border-top:1px solid var(--border);font-size:14px}
.rk-no{display:flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:var(--primary-weak);color:var(--primary-ink);font-size:13px;font-weight:700}
.rk-mini .rk-no{width:22px;height:22px;font-size:12px}
li:first-child>.rk-no{background:var(--accent);color:#fff}
li:nth-child(2)>.rk-no{background:var(--accent-weak);color:var(--accent-ink)}
.rk-co,.rk-mini a{font-weight:700;line-height:1.4;color:var(--primary-ink);text-decoration:none;overflow-wrap:anywhere}
.rk-mini a{font-weight:600}
.rk-co:hover,.rk-mini a:hover{text-decoration:underline}
.rk-val{font-size:19px;font-weight:700;line-height:1.2;color:var(--accent-ink);font-variant-numeric:tabular-nums;white-space:nowrap;text-align:right}
.rk-val small{margin-left:1px;font-size:12px}
.rk-mini .rk-val{font-size:15px}
.rk-sub{grid-column:2/4;display:flex;flex-wrap:wrap;align-items:center;gap:2px 10px;font-size:12px;line-height:1.6;color:var(--muted)}
.rk-sub .chip{padding:0 8px;font-size:11px}
.rk-more{margin-top:auto;align-self:flex-end;font-size:14px;font-weight:700;text-decoration:none}
.rk-more:hover{text-decoration:underline}
.rk-more-sub{font-size:12px;font-weight:400;color:var(--muted)}
.rk-how .facts{margin-top:12px}
@media (max-width:640px){
  .rk-facts{gap:6px}
  .rk-facts li{font-size:13px}
  .rk-section{margin-top:28px}
  .rk-grid{grid-template-columns:1fr;gap:10px}
  .rk-box,.rk-tile{padding:12px 14px 10px}
  .rk-val{font-size:18px}
}
"""
