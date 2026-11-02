"""優待しらべ 後処理の共通部品（postprocess.py・x_posts.py・indexnow.py・add_news.py から使う）。"""
import datetime
import hashlib
import html as htmllib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
DATA = TOOLS / "data"
STATE = TOOLS / "state"
JST = datetime.timezone(datetime.timedelta(hours=9))

# 公開しないディレクトリ（サイトのページとして扱わない）
SKIP_DIRS = {"tools", ".git", ".github", "drafts"}


def load_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def config():
    return load_json(TOOLS / "config.json", {})


def today_jst():
    return datetime.datetime.now(JST).date()


def strip_tags(s):
    return htmllib.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def esc(s):
    return htmllib.escape(s or "", quote=True)


def sha(text):
    if isinstance(text, str):
        text = text.encode("utf-8")
    return hashlib.sha256(text).hexdigest()[:16]


def html_files():
    """サイトの HTML（tools/ などを除く）を、ROOT からの相対パス（/ 区切り）で返す。"""
    out = []
    for p in ROOT.rglob("*.html"):
        rel = p.relative_to(ROOT)
        if rel.parts and rel.parts[0] in SKIP_DIRS:
            continue
        out.append(rel.as_posix())
    return sorted(out)


def prefix_for(rel):
    """ページからサイトの根までの相対パス（"" か "../"）。"""
    depth = rel.count("/")
    return "../" * depth


def url_for(rel, site_url):
    if rel == "index.html":
        return site_url + "/"
    return site_url + "/" + rel


def load_companies():
    """assets/companies.js（window.YUTAI_COMPANIES = [...]）を読む。"""
    p = ROOT / "assets" / "companies.js"
    text = p.read_text(encoding="utf-8")
    m = re.search(r"=\s*(\[.*\])\s*;?\s*$", text, re.S)
    if not m:
        return []
    return json.loads(m.group(1))


def shorten_company_name(formal):
    """題や見出し用に「株式会社」を外す（前後どちらでも。全角・半角の空白も外す）。"""
    s = re.sub(r"^[\s　]*株式会社[\s　]*", "", formal)
    s = re.sub(r"[\s　]*株式会社[\s　]*$", "", s)
    return s.strip() or formal


def x_weighted_length(text):
    """X の文字数の数え方（URL は 23、全角などは 2、半角は 1）。"""
    n = 0
    for part in re.split(r"(https?://\S+)", text):
        if re.match(r"https?://", part):
            n += 23
            continue
        for ch in part:
            cp = ord(ch)
            if (0x0000 <= cp <= 0x10FF) or (0x2000 <= cp <= 0x200D) or (0x2010 <= cp <= 0x201F) or (0x2032 <= cp <= 0x2037):
                n += 1
            else:
                n += 2
    return n


WEEKDAYS = "月火水木金土日"


def jp_date(d, with_year=False):
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d)
    s = f"{d.month}月{d.day}日（{WEEKDAYS[d.weekday()]}）"
    return (f"{d.year}年" + s) if with_year else s
