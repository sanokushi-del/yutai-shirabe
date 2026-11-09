# tools/ — 改善案12（C-1〜C-12）の後処理

サイトを作り直した（生成した）あとに、次を実行してください。何度実行しても結果は同じです。

```
python tools/postprocess.py
```

- 必要なもの: Python 3.9 以上。共有用画像（C-11）を作るには Pillow（`pip install pillow`）と日本語のフォント。
- フォントは `tools/config.json` の `og_fonts` の順に探します。`tools/fonts/` に Noto Sans JP（Bold と Regular）を置くのがおすすめです（Google Fonts から入手。`tools/fonts/` は公開しません）。
- 画像を作らずに済ませるとき: `python tools/postprocess.py --no-og`
- 書き込まずに確かめるとき: `python tools/postprocess.py --check`

生成のプログラムに同じ変更を取り込めたら、その項目は後処理から外せます（下の表の「どこで」を参照）。

## 何をしているか

| 項目 | 内容 | どこで |
|---|---|---|
| C-1 | IndexNow の鍵のファイル（`<鍵>.txt`）を置く。Search Console・Bing の所有確認の meta（`config.json` に値があるときだけ） | `postprocess.py`、`indexnow.py`、`.github/workflows/indexnow.yml` |
| C-2 | 会社ページの題・見出し・説明文。「株式会社」を外し、ブランド名を括弧で添える（`data/brand_aliases.json`）。正式な社名は「優待の条件」の表の「社名」に出す | `step_companies` |
| C-3 | 月のページの年を、次に来る権利確定日の年にする（11月に作ると、1〜10月は翌年） | `step_titles` |
| C-4 | 目次・初心者・優待の変化のページの題を、検索される言い方にする | `step_titles`（`PHRASES`） |
| C-5 | 会社ページの定型文を短くし、全文は `method.html` の「会社ページの補足」「項目の意味」へ | `BOILERPLATE`、`step_method` |
| C-6 | 株数ごとの優待内容の表（`data/tiers.json` に入れた会社だけ） | `step_companies` |
| C-7 | サイトマップの lastmod を、題・説明文・本文が変わった日にする（`state/lastmod.json`） | `step_sitemap` |
| C-8 | 中身の薄い一覧を noindex にしてサイトマップから外す（`NOINDEX_PAGES`） | `step_titles` |
| C-9 | 新設・変更・廃止のお知らせのページ `news/index.html` と RSS `news/feed.xml`（`data/news.json`） | `step_news`、`add_news.py` |
| C-10 | X の投稿文と note の下書き、運営者の JSON-LD の sameAs、運営者情報の X のリンク（`config.json` の `x_url`） | `x_posts.py`、`step_head` |
| C-11 | 会社ごとの共有用画像 `assets/og/c/<コード>.png`（写真のある会社は `.jpg`） | `og_images.py` |
| C-12 | カレンダーの購読（webcal・Google カレンダー）の案内、`yutai.ics` の更新間隔 | `step_calendar` |

全ページに `<meta name="robots" content="max-image-preview:large">` も足します（noindex のページを除く）。

ランキングの目次（`rank/index.html`）は、各ランキングのページ（`rank/*.html`）の表から上位3社を読み取って、カードの形に組み直します（`rank_index.py`、`step_rank_index`）。節の分け方・短い名前・式は `rank_index.py` の `SECTIONS`・`LABEL`・`FORMULA` で変えられます。

見やすさの直し（`readability.py`、`step_readability`）:

- 見出しの帯で、今いるページのタブを色で示します（`aria-current`）。「ランキング」のタブは、そのページにいるときだけ地の色が付きます。
- 一覧へのリンク（`ul.links`、会社ページの「同じ月・同じ種類の会社」）を、カードにします。社数は札にします。
- 表の会社名の列を広げ、下線を消します（パソコンの幅）。
- 月別カレンダーの表は、月の名前をその月の一覧へのリンクにし、スマホでは1か月を1枚のカードにします。
- ランキングのページの「計算の決め方・基準の日・並べ方・対象外の会社」を、開け閉めできる箱にします（ランキングを先に見せる）。
- スマホでは、トップの「条件で探す」の入力欄を2列にします。
- 作り方と限界のページの先頭に目次を置きます。
- 権利落ちの統計の表が、パソコンの幅に収まるようにします。
- お知らせは、1件ずつのカードと、種類ごとの色の札にします。

## 手で入れるデータ

### 株数ごとの優待内容（C-6）: `data/tiers.json`

会社の株主優待ページを開いて確かめた内容だけを入れてください。`source_url` と `checked` が無い会社は表を出しません。
よく検索される会社と公式ページの場所は `data/tiers.todo.json` にあります。

```json
{
  "2702": {
    "checked": "2026-11-05",
    "source_url": "https://www.mcd-holdings.co.jp/ir/individual/shareholder_benefits/",
    "source_label": "日本マクドナルドホールディングスの株主優待ページ",
    "record": "6月末・12月末",
    "condition": "（公式ページの保有の条件を、自分の言葉で）",
    "tiers": [
      {"shares": "100株以上300株未満", "content": "（公式ページの内容）"},
      {"shares": "300株以上500株未満", "content": "（公式ページの内容）"}
    ],
    "notes": ["有効期限・発送の時期など（自分の言葉で）"]
  }
}
```

表がある会社は、説明文（description）にも最初の段（例「100株以上で○○」）が入ります。

### 新設・変更・廃止のお知らせ（C-9）: `data/news.json`

**自動：** `.github/workflows/tdnet-news.yml` が毎日（日本時間 18:37 と 21:43）TDnet の一覧から表題に「優待」を含む発表を拾い（`tools/tdnet_news.py`）、表題・種類・PDF の URL を `data/news.json` に足して公開します。要約は自動では書きません（`"auto": true` の行）。要約を足したいときは、その行の `summary` を書き換えてください。
種類（新設・変更など）は表題の「優待」を含む部分から判定します（「（開示事項の経過）」は「その他」）。決め方を変えたあと、自動で足した行の種類を付け直すときは `python tools/tdnet_news.py --reclassify` です（手で足した行は変えません）。
トップのページの「株主優待の新設・変更・廃止」の欄（新しい順に5件。スマホは3件）も、同じデータから作ります。

**手で足すとき：** TDnet（適時開示情報閲覧サービス）で「優待」を含む発表を見て、確かめたものを足します。

**大事：** Actions が main に直接書き込むので、サイトを作り直す前に必ず `git pull` してください。

```
python tools/add_news.py --date 2026-11-04 --code 1234 --kind 新設 --title "株主優待制度の新設に関するお知らせ" --summary "100株以上にQUOカード1,000円分（3月末、年1回）" --url "https://..." --label TDnet
python tools/postprocess.py
```

- 1件以上あると、見出しの帯に「新設・廃止」のリンクが出ます。
- `config.json` の `news_min_entries_to_index`（初めは3）件より少ないうちは、お知らせのページを noindex にしてサイトマップに入れません（中身の薄いページを検索に出さないため）。

### ブランド名（C-2）: `data/brand_aliases.json`

社名とは違う店名・ブランド名でよく検索される会社だけ（`"コード": "ブランド名"`）。社名にもうその語が入っているときは使いません。

## 設定: `config.json`

| キー | 使いみち |
|---|---|
| `google_site_verification` | Search Console の HTML タグで所有確認するときの content の値（ドメイン プロパティを DNS で確認するなら空のまま） |
| `bing_site_verification` | Bing Webmaster Tools の `msvalidate.01` の値（Search Console から取り込むなら空のまま） |
| `indexnow_key` | IndexNow の鍵。変えたら、根の `<鍵>.txt` も変わります（古い方は手で消す） |
| `x_url` | X のアカウントの URL。入れると運営者情報と JSON-LD（sameAs）に出ます |
| `note_url` | note の URL（JSON-LD の sameAs） |
| `news_min_entries_to_index` | お知らせのページを検索に出し始める件数 |

## IndexNow（C-1）

`.github/workflows/indexnow.yml` が、GitHub Pages の公開（pages-build-deployment）が終わるたびに、直前のコミットで変わったページを送ります。
全ページを送るときは、GitHub の Actions →「IndexNow」→「Run workflow」で all にチェック。手元からは `python tools/indexnow.py --all`。

## X の投稿文・note の下書き（C-10）

```
python tools/x_posts.py                  # 今日から30日分の投稿文 → drafts/x-posts-<日付>.md
python tools/x_posts.py --note 2027-03   # 2027年3月権利の note 下書き → drafts/note-2027-03.md
```

`drafts/` は公開しません。投稿は手で行います。会社の写真は、会社から「サイトへの掲載」の許可をもらったものなので、X に画像として直接載せず、URL のカード（共有用画像）で見せてください。

## 状態のファイル（消さない）

- `state/lastmod.json` … ページごとの中身のハッシュと、変わった日（C-7）
- `state/og.json` … 共有用画像の入力のハッシュ（入力が同じなら作り直さない）
