"""C-11 会社ごとの共有用画像（OG 画像 1200×630）を作る。

変わりにくい項目（社名・コード・市場・業種・権利月・必要株数・もらえる品・継続保有・写真）だけを描くので、
株価が変わっても画像は作り直されない。入力が同じなら作り直さない（tools/state/og.json に入力のハッシュを残す）。
"""
import io
from pathlib import Path

from pplib import ROOT, STATE, load_json, save_json, sha

TEMPLATE_VERSION = "1"
W, H = 1200, 630
BG = (247, 244, 238)
SURFACE = (255, 255, 255)
TEXT = (29, 42, 51)
MUTED = (94, 106, 114)
PRIMARY = (31, 95, 110)
PRIMARY_INK = (22, 70, 82)
ACCENT = (200, 102, 47)
ACCENT_INK = (162, 74, 27)
BORDER = (228, 223, 213)
OUT_DIR = ROOT / "assets" / "og" / "c"


def _find_font(candidates):
    for c in candidates:
        p = Path(c)
        if not p.is_absolute():
            p = ROOT / c
        if p.exists():
            return str(p)
    return None


class Fonts:
    def __init__(self, cfg):
        from PIL import ImageFont  # noqa: F401  (Pillow が無いときはここで ImportError)

        fonts = cfg.get("og_fonts", {})
        self.bold_path = _find_font(fonts.get("bold", []))
        self.regular_path = _find_font(fonts.get("regular", [])) or self.bold_path
        if not self.bold_path:
            self.bold_path = self.regular_path
        if not self.bold_path:
            raise FileNotFoundError("日本語のフォントが見つかりません（tools/config.json の og_fonts）")
        # 太字のファイルが無く、普通の太さで代用するときは縁取りで太く見せる
        self.fake_bold = self.bold_path == self.regular_path
        self._cache = {}

    def get(self, size, bold=False):
        from PIL import ImageFont

        key = (size, bold)
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(self.bold_path if bold else self.regular_path, size)
        return self._cache[key]

    @property
    def name(self):
        return Path(self.bold_path).name + "/" + Path(self.regular_path).name


def _text_w(draw, text, font):
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    return r - l


def _wrap(draw, text, font, max_w, max_lines):
    lines, cur = [], ""
    for ch in text:
        if _text_w(draw, cur + ch, font) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
            if len(lines) == max_lines:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    consumed = sum(len(x) for x in lines)
    if consumed < len(text):
        last = lines[-1]
        while last and _text_w(draw, last + "…", font) > max_w:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


def _draw_text(draw, xy, text, font, fill, fonts, bold=False):
    if bold and fonts.fake_bold:
        draw.text(xy, text, font=font, fill=fill, stroke_width=1, stroke_fill=fill)
    else:
        draw.text(xy, text, font=font, fill=fill)


def render_card(info, fonts, photo_path=None):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 上の帯（主の色から強調の色へ）
    for x in range(W):
        t = x / (W - 1)
        col = tuple(int(PRIMARY[i] * (1 - t) + ACCENT[i] * t) for i in range(3))
        d.line([(x, 0), (x, 9)], fill=col)
    # 白い面
    d.rounded_rectangle([40, 40, W - 40, H - 96], radius=28, fill=SURFACE, outline=BORDER, width=2)
    # 下の帯
    d.rectangle([0, H - 64, W, H], fill=PRIMARY)
    foot = "yutai-shirabe.com ・ 有価証券報告書から読み取った推定を含みます"
    _draw_text(d, (72, H - 50), foot, fonts.get(24), (255, 255, 255), fonts)

    has_photo = bool(photo_path and Path(photo_path).exists())
    text_right = 760 if has_photo else W - 88
    x0 = 88
    # サイト名
    d.rounded_rectangle([x0, 78, x0 + 34, 112], radius=8, fill=PRIMARY)
    d.polygon([(x0 + 10, 86), (x0 + 24, 86), (x0 + 24, 106), (x0 + 17, 101), (x0 + 10, 106)], fill=(255, 255, 255))
    _draw_text(d, (x0 + 46, 76), "優待しらべ ・ 株主優待の条件", fonts.get(26, True), PRIMARY_INK, fonts, bold=True)

    # 社名（2行まで。長いときは小さくする）
    name = info["label"]
    y = 124
    for size in (62, 56, 50, 46):
        f = fonts.get(size, True)
        lines = _wrap(d, name, f, text_right - x0, 2)
        if len(lines) == 1 or size == 46:
            break
        if not lines[-1].endswith("…"):
            break
    for ln in lines:
        _draw_text(d, (x0, y), ln, f, TEXT, fonts, bold=True)
        y += int(size * 1.18)
    # 「の株主優待」と市場・業種
    sub = "の株主優待"
    _draw_text(d, (x0, y), sub, fonts.get(34, True), ACCENT_INK, fonts, bold=True)
    meta = "  ".join(x for x in [info.get("code", ""), info.get("market", ""), info.get("sector", "")] if x)
    _draw_text(d, (x0 + _text_w(d, sub, fonts.get(34, True)) + 24, y + 6), meta, fonts.get(26), MUTED, fonts)
    y += 54

    rows = [
        ("権利確定月", info.get("months") or "記載なし"),
        ("必要株数", info.get("shares") or "記載なし"),
        ("もらえる品", info.get("items") or "記載なし"),
    ]
    if info.get("hold") and "記載なし" not in info["hold"]:
        rows.append(("継続保有", info["hold"]))
    lab_f, val_f = fonts.get(24), fonts.get(30, True)
    step = 52 if len(lines) > 1 else 56
    for lab, val in rows[:4]:
        if y + 44 > H - 100:
            break
        d.rounded_rectangle([x0, y + 4, x0 + 146, y + 40], radius=8, fill=(228, 240, 241))
        lw = _text_w(d, lab, lab_f)
        _draw_text(d, (x0 + (146 - lw) // 2, y + 6), lab, lab_f, PRIMARY_INK, fonts)
        v = _wrap(d, val, val_f, text_right - (x0 + 166), 1)[0]
        _draw_text(d, (x0 + 166, y + 1), v, val_f, TEXT, fonts, bold=True)
        y += step

    if has_photo:
        try:
            ph = Image.open(photo_path).convert("RGB")
            box_w, box_h = 340, 380
            ph.thumbnail((box_w, box_h))
            px = W - 88 - box_w + (box_w - ph.width) // 2
            py = 78 + (box_h - ph.height) // 2 + 20
            mask = Image.new("L", ph.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, ph.width - 1, ph.height - 1], radius=16, fill=255)
            d.rounded_rectangle([px - 6, py - 6, px + ph.width + 5, py + ph.height + 5], radius=20, fill=BORDER)
            img.paste(ph, (px, py), mask)
        except Exception:  # 写真が読めなくてもカードは作る
            has_photo = False
    return img, has_photo


def encode(img, has_photo):
    buf = io.BytesIO()
    if has_photo:
        img.save(buf, "JPEG", quality=78, optimize=True, progressive=True)
        return buf.getvalue(), ".jpg"
    q = img.quantize(colors=40, method=2, dither=0)
    q.save(buf, "PNG", optimize=True)
    return buf.getvalue(), ".png"


def build_all(cards, cfg, log):
    """cards: {code: info}。info には label/code/market/sector/months/shares/items/hold と photo（パス）。
    戻り値: {code: 公開パス（assets/og/c/xxxx.png など）}。"""
    try:
        fonts = Fonts(cfg)
    except (ImportError, FileNotFoundError) as e:
        log(f"  OG 画像: 作れません（{e}）。前に作った画像はそのまま使います。")
        fonts = None
    state_path = STATE / "og.json"
    state = load_json(state_path, {})
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result, made = {}, 0
    for code, info in sorted(cards.items()):
        photo = info.get("photo")
        photo_hash = sha(Path(photo).read_bytes()) if photo and Path(photo).exists() else ""
        key = sha("|".join([TEMPLATE_VERSION, fonts.name if fonts else "", info["label"], info.get("code", ""),
                            info.get("market", ""), info.get("sector", ""), info.get("months", ""),
                            info.get("shares", ""), info.get("items", ""), info.get("hold", ""), photo_hash]))
        prev = state.get(code)
        if prev and (ROOT / prev["path"]).exists() and (prev["key"] == key or fonts is None):
            result[code] = prev["path"]
            continue
        if fonts is None:
            continue
        img, has_photo = render_card(info, fonts, photo)
        data, ext = encode(img, has_photo)
        rel = f"assets/og/c/{code}{ext}"
        for old_ext in (".png", ".jpg"):
            old = OUT_DIR / f"{code}{old_ext}"
            if old_ext != ext and old.exists():
                old.unlink()
        (ROOT / rel).write_bytes(data)
        state[code] = {"key": key, "path": rel}
        result[code] = rel
        made += 1
    # ページが無くなった会社の画像を消す
    for code in list(state):
        if code not in cards:
            p = ROOT / state[code]["path"]
            if p.exists():
                p.unlink()
            del state[code]
    save_json(state_path, state)
    log(f"  OG 画像: {made} 枚を作成（全 {len(result)} 社）")
    return result
