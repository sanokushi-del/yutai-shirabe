"""見やすさの直し（postprocess.py の step_readability から使う）。

- 見出しの帯（タブ）: 今いるページ・その仲間のページのタブに aria-current を付けて、色で示す
- リンクの一覧（ul.links）: 社数を札にして、1件ずつのカードにする
- 作り方と限界（method.html）: ページの先頭に目次
- ランキングのページ: 計算の決め方などの説明を、開け閉めできる箱に
- 月別カレンダー（calendar/index.html）: 月の名前をその月の一覧へのリンクにし、スマホでは1か月を1枚のカードにする
CSS は CSS（step_css が site.css の pp:start〜pp:end に入れる）。どれも何度かけても同じ結果になる。
"""
import posixpath
import re

from pplib import esc, strip_tags

# ページ → 光らせるタブ（リンク先）。c/ の会社ページは、パンくずと同じく「条件で探す」の仲間
SECTION_PREFIX = [("rank/", "rank/index.html"), ("calendar/", "calendar/index.html"), ("news/", "news/index.html"),
                  ("list/", "list/index.html"), ("c/", "list/index.html")]
SECTION_PAGES = ["guide/rights-last-day.html", "guide/ex-rights-stats.html", "method.html"]


def nav_target(rel):
    if rel in SECTION_PAGES:
        return rel
    for pre, target in SECTION_PREFIX:
        if rel.startswith(pre):
            return target
    return None


def mark_nav(h, rel):
    m = re.search(r'(<nav class="site-nav"[^>]*>)(.*?)(</nav>)', h, re.S)
    if not m:
        return h
    inner = re.sub(r' aria-current="[^"]*"', "", m.group(2))
    target = nav_target(rel)
    if target:
        base = posixpath.dirname(rel)

        def mark(a):
            href = a.group(2)
            if re.match(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:|/|#)", href):
                return a.group(0)
            path = posixpath.normpath(posixpath.join(base, href.split("#")[0]))
            if path != target:
                return a.group(0)
            return a.group(1) + f' aria-current="{"page" if rel == target else "true"}"' + a.group(3)

        inner = re.sub(r'(<a href="([^"]*)")([^>]*>)', mark, inner)
    return h[:m.start(2)] + inner + h[m.end(2):]


def link_counts(h):
    """ul.links の「…</a>（123社）」の社数を札にする。"""
    def fix(m):
        return re.sub(r"</a>（([\d,]+社)）</li>", r'</a><span class="links-count">\1</span></li>', m.group(0))
    return re.sub(r'<ul class="links">.*?</ul>', fix, h, flags=re.S)


METHOD_IDS = {"データの作り方": "making", "限界（先にお読みください）": "limits", "既知の誤り": "errors", "更新": "update"}


def method_toc(h):
    h = re.sub(r'<nav class="toc"[^>]*>.*?</nav>\n?', "", h, flags=re.S)
    used = set(re.findall(r' id="([^"]+)"', h))

    def add_id(m):
        text = m.group(1)
        new = METHOD_IDS.get(strip_tags(text))
        if not new or new in used:
            return m.group(0)
        used.add(new)
        return f'<h2 id="{new}">{text}</h2>'

    h = re.sub(r"<h2>(.*?)</h2>", add_id, h)
    heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', h)
    if len(heads) < 3:
        return h
    pills = "".join(f'<li><a class="pill" href="#{i}">{esc(re.sub(r"（.*?）", "", strip_tags(t)))}</a></li>' for i, t in heads)
    toc = f'<nav class="toc" aria-label="このページの目次"><ul class="pills">{pills}</ul></nav>\n'
    return re.sub(r"(<h1[^>]*>.*?</h1>\n?)", lambda mm: mm.group(1) + toc, h, count=1, flags=re.S)


def stats_ranges(h):
    """権利落ちの統計の表の「95%区間 X〜Y」の X〜Y を折り返さない（折り返すのは「95%区間」の後ろだけ）。"""
    return re.sub(r'(<span class="sub">95%区間 )([^<]+)(</span>)', r'\1<span class="nw">\2</span>\3', h)


def rank_facts_fold(h):
    """ランキングのページの「計算の決め方・基準の日・並べ方・対象外の会社」を、開け閉めできる箱にする（ランキングを先に見せる）。"""
    if 'class="rank-about"' in h:
        return h
    m = re.search(r'<dl class="facts rank-facts">.*?</dl>', h, re.S)
    if not m:
        return h
    f = re.search(r"<dt>計算の決め方</dt>\s*<dd>(.*?)</dd>", m.group(0), re.S)
    formula = strip_tags(f.group(1)).split("。")[0] if f else ""
    summary = ('<summary>計算の決め方・基準の日・対象の会社'
               + (f'<span class="rank-about-formula">{esc(formula)}</span>' if formula else "") + "</summary>")
    return h[:m.start()] + f'<details class="rank-about">{summary}{m.group(0)}</details>' + h[m.end():]


CAL_LABELS = [None, ("権利付き最終日", "最終日"), ("社数", None), ("必要株数100株以下の社数", "100株以下"), ("ページ", None)]


def calendar_cards(h):
    m = re.search(r'(<div class="table-wrap"(?: data-cards)? role="region" aria-label="次の12ヶ月の権利付き最終日"[^>]*>)(.*?)(</table>)',
                  h, re.S)
    if not m:
        return h
    opener = m.group(1) if " data-cards" in m.group(1) else m.group(1).replace('class="table-wrap"', 'class="table-wrap" data-cards', 1)
    table = m.group(2)

    def fix_row(rm):
        row = rm.group(1)
        cells = re.findall(r"<td([^>]*)>(.*?)</td>", row, re.S)
        if len(cells) != len(CAL_LABELS):
            return rm.group(0)
        page = re.search(r'<a href="(\d{4}-\d{2}\.html)">', cells[-1][1])
        out = []
        for i, (attrs, inner) in enumerate(cells):
            attrs = re.sub(r' data-(?:label|short)="[^"]*"', "", attrs)
            classes = [c for c in re.findall(r'class="([^"]*)"', attrs)[0].split() if c not in ("name", "cal-month")] if "class=" in attrs else []
            attrs = re.sub(r' class="[^"]*"', "", attrs)
            if i == 0:
                label = strip_tags(inner)
                inner = f'<a href="{page.group(1)}">{esc(label)}</a>' if page else esc(label)
                classes += ["name", "cal-month"]
            else:
                lab, short = CAL_LABELS[i]
                attrs += f' data-label="{lab}"' + (f' data-short="{short}"' if short else "")
            cls = f' class="{" ".join(classes)}"' if classes else ""
            out.append(f"<td{cls}{attrs}>{inner}</td>")
        return "<tr>" + "".join(out) + "</tr>"

    table = re.sub(r"<tr>((?:(?!</tr>).)*?<td.*?)</tr>", fix_row, table, flags=re.S)
    return h[:m.start(1)] + opener + table + h[m.end(2):]


CSS = """/* 見やすさの直し（tools/readability.py） */
.site-nav a.nav-rank{background:none;color:var(--accent-ink)}
.site-nav a[aria-current]{background:var(--primary-weak);color:var(--primary-ink);font-weight:700;box-shadow:inset 0 -3px 0 var(--primary)}
.site-nav a.nav-rank[aria-current]{background:var(--accent-weak);color:var(--accent-ink);box-shadow:inset 0 -3px 0 var(--accent)}
td.name a{font-weight:600;text-decoration:none}
td.name a:hover{text-decoration:underline}
ul.links{columns:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:8px;list-style:none;margin:10px 0 20px;padding:0}
ul.links li{position:relative;display:flex;align-items:center;justify-content:space-between;gap:4px 10px;margin:0;padding:10px 12px;background:var(--surface);border:1px solid var(--border);border-radius:10px;box-shadow:var(--shadow);font-size:13px;line-height:1.5;color:var(--muted)}
ul.links li:hover{border-color:var(--primary)}
ul.links a{font-size:15px;font-weight:700;color:var(--primary-ink);text-decoration:none}
ul.links a::after{content:"";position:absolute;inset:0;border-radius:10px}
ul.links li:hover a{text-decoration:underline}
.links-count{flex:none;padding:1px 10px;border-radius:999px;background:var(--primary-weak);color:var(--primary-ink);font-size:12px;font-weight:700;white-space:nowrap}
ul.related{list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px;padding:0}
ul.related li{position:relative;margin:0;padding:8px 12px;background:var(--surface);border:1px solid var(--border);border-radius:10px;box-shadow:var(--shadow)}
ul.related li:hover{border-color:var(--primary)}
ul.related a{font-weight:700;color:var(--primary-ink);text-decoration:none}
ul.related a::after{content:"";position:absolute;inset:0;border-radius:10px}
ul.related li:hover a{text-decoration:underline}
ul.related .small{display:block;margin-top:2px}
.toc{margin:4px 0 20px}
.toc .pills{display:flex;flex-wrap:wrap;gap:8px;list-style:none;margin:0;padding:0}
.toc .pills li{margin:0}
h2[id]{scroll-margin-top:8px}
.bar-row{grid-template-columns:8em minmax(0,1fr) 5.5em}
.table-wrap:has(th.group) td{white-space:normal}
.table-wrap:has(th.group) td:first-child{min-width:3.5em}
.nw{white-space:nowrap}
.news-list{list-style:none;margin:8px 0 0;padding:0}
.news-list li.news-item{display:grid;grid-template-columns:8.5em minmax(0,1fr);gap:4px 16px;margin:0 0 8px;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow)}
.news-meta{display:flex;flex-direction:column;align-items:flex-start;gap:6px}
.news-meta time{font-size:14px;font-weight:600;color:var(--muted)}
.news-body p{margin:0}
.news-co{font-size:16px;font-weight:700;color:var(--primary-ink)}
.news-co a{color:var(--primary-ink);text-decoration:none}
.news-co a:hover{text-decoration:underline}
.news-title{margin-top:2px;font-size:15px}
.news-summary{margin-top:8px!important;padding:8px 12px;border-radius:8px;background:var(--bg);font-size:14px}
.news-kind{margin:0}
.kind-new{background:#e2f2e5;color:#1d6630}
.kind-up{background:var(--accent-weak);color:var(--accent-ink)}
.kind-change{background:var(--primary-weak);color:var(--primary-ink)}
.kind-end{background:#fbe3e1;color:#992b22}
.kind-other{background:#ebe8e1;color:var(--muted)}
.news-note .news-kind{margin-right:4px}
details.rank-about{margin:12px 0;background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow)}
details.rank-about>summary{cursor:pointer;padding:10px 14px;font-weight:600;line-height:1.5;color:var(--primary-ink)}
details.rank-about>summary::marker{color:var(--primary)}
.rank-about-formula{display:block;font-size:13px;font-weight:400;color:var(--muted)}
details.rank-about[open]>summary{border-bottom:1px solid var(--border)}
details.rank-about>dl.facts{margin:0;border:none;border-radius:0 0 12px 12px;box-shadow:none}
.news-top{margin:14px 0 18px;padding:12px 16px 10px;background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow)}
.news-top .rank-head h2{border-left-color:var(--primary)}
.news-top ul{list-style:none;margin:8px 0 6px;padding:0}
.news-top li{display:grid;grid-template-columns:7.2em auto minmax(0,1fr);gap:2px 10px;align-items:baseline;margin:0;padding:8px 0;border-top:1px solid var(--border);font-size:14px;line-height:1.55}
.news-top time{font-size:13px;font-weight:600;color:var(--muted);white-space:nowrap}
.news-top-text strong a{color:var(--primary-ink);text-decoration:none}
.news-top-text strong a:hover{text-decoration:underline}
.news-top>.small{margin:0}
.news-top .news-kind{justify-self:start}
@media (min-width:641px){
  td.name{min-width:12.5em}
  td[data-label="継続保有"] .chip{white-space:normal;border-radius:10px}
  td.cal-month{min-width:0;white-space:nowrap}
}
@media (max-width:640px){
  .filters{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
  .filters>div:first-child{grid-column:1/-1}
  .filters label{font-size:13px}
  .filters input[type=text],.filters select{box-sizing:border-box;height:44px;width:100%}
  .news-top{padding:10px 12px 8px}
  .news-top li{grid-template-columns:auto minmax(0,1fr)}
  .news-top-text{grid-column:1/-1}
  .news-top li:nth-child(n+4){display:none}
  ul.links{grid-template-columns:1fr;gap:6px}
  ul.links li{padding:9px 12px}
  ul.links a{font-size:14px}
  .bar-row{grid-template-columns:6.5em minmax(0,1fr) 4.5em}
  .table-wrap[aria-label^="次の権利確定日"] th,.table-wrap[aria-label^="次の権利確定日"] td,
  .table-wrap[aria-label="計算の例"] th,.table-wrap[aria-label="計算の例"] td{padding:8px 6px;font-size:13px;white-space:normal;word-break:keep-all}
  .table-wrap[data-cards] td[data-label="権利付き最終日"]{display:block;margin:0 0 2px}
  .table-wrap[data-cards] td[data-label="ページ"]{display:block;margin-top:4px}
  .table-wrap[data-cards] td[data-label="ページ"]::before{content:none}
  .news-list li.news-item{grid-template-columns:1fr;padding:12px 14px}
  .news-meta{flex-direction:row;align-items:center;gap:8px}
}
"""
