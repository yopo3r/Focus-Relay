"""Imágenes para compartir (racha, resumen de un período, logro) dibujadas con Pillow.

Tienen la identidad de la app (degradado del tema activo) y no incluyen datos sensibles: solo cifras
agregadas, y el nombre únicamente si el usuario lo activa. Tamaños: cuadrada 1080×1080 y vertical 1080×1920.
"""
import glob
import io
import math
import os
from datetime import date

from PIL import Image, ImageDraw, ImageFont

import i18n
from i18n import t

SIZES = {"square": (1080, 1080), "story": (1080, 1920)}

_FONT_DIRS = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.local/share/fonts"),
              os.path.expanduser("~/.fonts"), "C:/Windows/Fonts", "/System/Library/Fonts",
              "/System/Library/Fonts/Supplemental", "/Library/Fonts"]
_LATIN = {True: ["Inter-Bold.otf", "Inter-Bold.ttf", "Inter-SemiBold.otf", "Inter-SemiBold.ttf", "segoeuib.ttf",
                 "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"],
          False: ["Inter-Regular.otf", "Inter-Regular.ttf", "Inter-Medium.otf", "segoeui.ttf",
                  "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf", "arial.ttf"]}
_CJK = {True: ["NotoSansCJK-Bold.ttc", "NotoSansCJKsc-Bold.otf", "msyhbd.ttc", "msyh.ttc", "PingFang.ttc",
               "NotoSansSC-Bold.otf", "simhei.ttf", "wqy-microhei.ttc"],
        False: ["NotoSansCJK-Regular.ttc", "NotoSansCJKsc-Regular.otf", "msyh.ttc", "PingFang.ttc",
                "NotoSansSC-Regular.otf", "simhei.ttf", "wqy-microhei.ttc"]}
# Fuentes específicas para japonés y coreano (el kana y el hangul no están en las fuentes chinas de Windows)
_JA = {True: ["NotoSansCJK-Bold.ttc", "NotoSansJP-Bold.otf", "YuGothB.ttc", "meiryob.ttc", "HiraginoSans-W6.ttc"],
       False: ["NotoSansCJK-Regular.ttc", "NotoSansJP-Regular.otf", "YuGothM.ttc", "meiryo.ttc", "HiraginoSans-W3.ttc"]}
_KO = {True: ["NotoSansCJK-Bold.ttc", "NotoSansKR-Bold.otf", "malgunbd.ttf", "AppleSDGothicNeo.ttc", "NanumGothicBold.ttf"],
       False: ["NotoSansCJK-Regular.ttc", "NotoSansKR-Regular.otf", "malgun.ttf", "AppleSDGothicNeo.ttc", "NanumGothic.ttf"]}
_found = {}


def _find(names):
    for name in names:
        key = ("f", name)
        if key not in _found:
            hit = None
            for d in _FONT_DIRS:
                if os.path.isdir(d):
                    m = glob.glob(os.path.join(d, "**", name), recursive=True)
                    if m:
                        hit = m[0]
                        break
            _found[key] = hit
        if _found[key]:
            return _found[key]
    return None


def font(size, bold=False, cjk=False, script=None):
    table = {"ja": _JA, "ko": _KO}.get(script, _CJK) if cjk else _LATIN
    path = _find(table[bold]) or (_find(_CJK[bold]) if cjk else None) or _find(_LATIN[bold])
    try:
        if path:
            return ImageFont.truetype(path, int(size))
        return ImageFont.load_default(int(size))
    except (OSError, TypeError):
        return ImageFont.load_default()


def _script(s):
    """'ja' si hay kana, 'ko' si hay hangul, 'zh' si solo hay ideogramas, None si es texto latino/cirílico."""
    found = None
    for c in str(s):
        o = ord(c)
        if 0x3040 <= o <= 0x30FF:
            return "ja"
        if 0xAC00 <= o <= 0xD7AF or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F:
            return "ko"
        if o >= 0x2E80:
            found = "zh"
    return found


def _has_cjk(s):
    return _script(s) is not None


def F(s, size, bold=False):
    sc = _script(s)
    return font(size, bold, sc is not None, sc)


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _mix(a, b, t_):
    return tuple(round(x + (y - x) * t_) for x, y in zip(_rgb(a) if isinstance(a, str) else a, _rgb(b) if isinstance(b, str) else b))


def _gradient(w, h, a, b, c):
    img = Image.new("RGB", (w, h))
    px = img.load()
    A, B, C = _rgb(a), _rgb(b), _rgb(c)
    for y in range(h):
        for x in range(w):
            k = (x * 0.35 + y * 0.65) / (w * 0.35 + h * 0.65)
            px[x, y] = _mix(A, B, k / 0.6) if k < 0.6 else _mix(B, C, (k - 0.6) / 0.4)
    return img


class Canvas:
    """Dibuja a 2x y reduce al final. Cada forma se pinta en una capa pequeña y se mezcla (alfa real)."""

    def __init__(self, size, pal):
        self.W, self.H = size
        self.k = 2
        self.pal = pal
        self.img = _gradient(self.W // 4, self.H // 4, pal["A"], pal["B"], pal["C"]).resize(
            (self.W * self.k, self.H * self.k), Image.BICUBIC).convert("RGBA")
        self.fg = pal["FG"]
        self.U = self.W / 1080.0
        self.tall = self.H > self.W

    def s(self, v):
        return int(round(v * self.k))

    def rgba(self, color, a=1.0):
        return _rgb(color) + (int(255 * a),)

    def _paint(self, box, fn):
        """box en px 2x (x1, y1, x2, y2); fn(draw, ox, oy) dibuja con coordenadas desplazadas."""
        x1, y1, x2, y2 = (int(v) for v in box)
        pad = 4
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(self.img.width, x2 + pad), min(self.img.height, y2 + pad)
        if x2 <= x1 or y2 <= y1:
            return
        layer = Image.new("RGBA", (x2 - x1, y2 - y1), (0, 0, 0, 0))
        fn(ImageDraw.Draw(layer), x1, y1)
        self.img.alpha_composite(layer, dest=(x1, y1))

    def rect(self, x1, y1, x2, y2, r, fill=None, outline=None, width=0, alpha=1.0):
        box = [self.s(v) for v in (x1, y1, x2, y2)]
        self._paint(box, lambda d, ox, oy: d.rounded_rectangle(
            (box[0] - ox, box[1] - oy, box[2] - ox, box[3] - oy), radius=self.s(r),
            fill=self.rgba(fill, alpha) if fill else None,
            outline=self.rgba(outline, alpha) if outline else None, width=self.s(width)))

    def circle(self, cx, cy, r, fill=None, outline=None, width=0, alpha=1.0):
        box = [self.s(v) for v in (cx - r, cy - r, cx + r, cy + r)]
        self._paint(box, lambda d, ox, oy: d.ellipse(
            (box[0] - ox, box[1] - oy, box[2] - ox, box[3] - oy),
            fill=self.rgba(fill, alpha) if fill else None,
            outline=self.rgba(outline, alpha) if outline else None, width=self.s(width)))

    def text(self, x, y, s, size, bold=False, anchor="la", fill=None, alpha=1.0, maxw=None):
        size = int(size)
        f = F(s, size * self.k, bold)
        if maxw:
            while f.getlength(str(s)) > maxw * self.k and size > 14:
                size -= 2
                f = F(s, size * self.k, bold)
        xy = (self.s(x), self.s(y))
        probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        box = probe.textbbox(xy, str(s), font=f, anchor=anchor)
        self._paint(box, lambda d, ox, oy: d.text((xy[0] - ox, xy[1] - oy), str(s), font=f,
                                                  fill=self.rgba(fill or self.fg, alpha), anchor=anchor))
        return size

    def width(self, s, size, bold=False):
        return F(s, size * self.k, bold).getlength(str(s)) / self.k

    def wrap(self, s, size, maxw, bold=False):
        f = F(s, size * self.k, bold)
        cjk = _script(s) in ("ja", "zh")
        words, lines, cur = (list(str(s)) if cjk else str(s).split(" ")), [], ""
        sep = "" if cjk else " "
        for w in words:
            test = (cur + sep + w) if cur else w
            if f.getlength(test) <= maxw * self.k:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def paragraph(self, cx, y, s, size, maxw, alpha=0.9, bold=False, gap=1.3, maxlines=4):
        lines = self.wrap(s, size, maxw, bold)[:maxlines]
        for i, line in enumerate(lines):
            self.text(cx, y + i * size * gap, line, size, bold=bold, anchor="ma", alpha=alpha)
        return y + len(lines) * size * gap

    def poly(self, pts, fill, alpha=1.0):
        P = [(self.s(x), self.s(y)) for x, y in pts]
        xs, ys = [p[0] for p in P], [p[1] for p in P]
        self._paint((min(xs), min(ys), max(xs), max(ys)), lambda d, ox, oy: d.polygon(
            [(x - ox, y - oy) for x, y in P], fill=self.rgba(fill, alpha)))

    def line(self, pts, fill, width, alpha=1.0):
        P = [(self.s(x), self.s(y)) for x, y in pts]
        w = self.s(width)
        xs, ys = [p[0] for p in P], [p[1] for p in P]
        self._paint((min(xs) - w, min(ys) - w, max(xs) + w, max(ys) + w), lambda d, ox, oy: (
            d.line([(x - ox, y - oy) for x, y in P], fill=self.rgba(fill, alpha), width=w, joint="curve"),
            [d.ellipse((x - ox - w / 2, y - oy - w / 2, x - ox + w / 2, y - oy + w / 2), fill=self.rgba(fill, alpha))
             for x, y in (P[0], P[-1])]))

    def logo(self, x, y, size):
        try:
            import icon_art
            lg = icon_art.draw(self.s(size), self.pal["A"], self.pal["C"], self.fg)
            self.img.alpha_composite(lg, dest=(self.s(x), self.s(y)))
        except Exception:
            pass

    def done(self):
        return self.img.resize((self.W, self.H), Image.LANCZOS).convert("RGB")


# --------------------------------------------------------------------------- iconos dibujados
def _bez(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        u = i / n
        a, b, c, d = (1 - u) ** 3, 3 * u * (1 - u) ** 2, 3 * u * u * (1 - u), u ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def flame(c, cx, cy, h, color, inner=None, alpha=1.0):
    """Llama estilizada de alto `h` centrada en (cx, cy)."""
    def shape(scale, dy=0.0):
        pts = (_bez((0, 1), (-1.0, 0.95), (-0.95, 0.05), (0.12, -1))
               + _bez((0.12, -1), (0.0, -0.45), (0.55, -0.35), (0.62, 0.0))[1:]
               + _bez((0.62, 0.0), (0.95, 0.25), (0.75, 0.95), (0, 1))[1:])
        return [(cx + x * h * 0.34 * scale, cy + (y * 0.5 * h * scale) + dy) for x, y in pts]
    c.poly(shape(1.0), color, alpha)
    if inner:
        c.poly(shape(0.52, h * 0.24), inner, alpha)


def clock_icon(c, cx, cy, r, color, bg):
    c.circle(cx, cy, r, outline=color, width=r * 0.16)
    c.line([(cx, cy), (cx, cy - r * 0.6)], color, r * 0.14)
    c.line([(cx, cy), (cx + r * 0.42, cy + r * 0.2)], color, r * 0.14)
    c.circle(cx, cy, r * 0.1, fill=color)


def check_icon(c, cx, cy, r, color):
    c.line([(cx - r * 0.55, cy + r * 0.02), (cx - r * 0.12, cy + r * 0.45), (cx + r * 0.6, cy - r * 0.42)], color, r * 0.24)


def list_icon(c, cx, cy, r, color):
    for i in (-1, 0, 1):
        y = cy + i * r * 0.5
        c.circle(cx - r * 0.5, y, r * 0.1, fill=color)
        c.rect(cx - r * 0.25, y - r * 0.07, cx + r * 0.6, y + r * 0.07, r * 0.07, fill=color)


def star_icon(c, cx, cy, r, color):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    c.poly(pts, color)


def trophy_icon(c, cx, cy, r, color):
    c.rect(cx - r * 0.5, cy - r * 0.7, cx + r * 0.5, cy + r * 0.1, r * 0.25, fill=color)
    c.rect(cx - r * 0.1, cy + r * 0.05, cx + r * 0.1, cy + r * 0.45, 0, fill=color)
    c.rect(cx - r * 0.42, cy + r * 0.42, cx + r * 0.42, cy + r * 0.62, r * 0.08, fill=color)
    for sgn in (-1, 1):
        c.circle(cx + sgn * r * 0.62, cy - r * 0.35, r * 0.2, outline=color, width=r * 0.1)


def family_icon(c, family, cx, cy, r, color, bg):
    if family == "streak":
        flame(c, cx, cy, r * 2.0, color, inner=bg, alpha=1.0)
    elif family == "hours":
        clock_icon(c, cx, cy, r * 0.8, color, bg)
    elif family == "sessions":
        check_icon(c, cx, cy, r * 0.9, color)
    elif family == "tasks":
        list_icon(c, cx, cy, r * 0.9, color)
    else:
        trophy_icon(c, cx, cy, r * 0.9, color)


# --------------------------------------------------------------------------- plantillas
def _header(c, name):
    m = 80
    c.logo(m, 62, 56)
    c.text(m + 70, 90, "Focus Relay", 28, bold=True, anchor="lm")
    if name:
        c.text(c.W - m, 90, name, 28, bold=True, anchor="rm", maxw=c.W * 0.4)
    return 170


def _footer(c, message):
    """Mensaje abajo + marca. Devuelve la y donde empieza (el contenido debe quedar por encima)."""
    m = 80
    lines = c.wrap(message, 34, c.W - 2 * m - 40)[:3] if message else []
    brand_y = c.H - 56
    top = brand_y - 40 - len(lines) * 44 - (16 if lines else 0)
    for i, line in enumerate(lines):
        c.text(c.W / 2, top + i * 44, line, 34, anchor="ma", alpha=0.95)
    c.text(c.W / 2, brand_y, t("shareFooter"), 22, anchor="mm", alpha=0.7)
    return top - 20


def _chips_row(c, y, items, h=112):
    f = 1.3 if c.tall else 1.0
    h = h * f
    widths = [max(c.width(str(v), 40 * f, True), c.width(l, 22 * f)) + 56 * f for l, v in items]
    gap, x = 20, 0
    x = (c.W - (sum(widths) + gap * (len(items) - 1))) / 2
    for (l, v), w in zip(items, widths):
        c.rect(x, y, x + w, y + h, 26, fill=c.fg, alpha=0.16)
        c.text(x + w / 2, y + h * 0.42, v, 40 * f, bold=True, anchor="mm")
        c.text(x + w / 2, y + h * 0.8, l, 22 * f, anchor="mm", alpha=0.85, maxw=w - 20)
        x += w + gap
    return y + h


def streak_card(c, data, name, message):
    top = _header(c, name)
    limit = _footer(c, message)
    f = 1.4 if c.tall else 1.0
    n = str(data["streak"])
    size = (190 if len(n) < 3 else 150) * f
    fl = 250 * f
    block = fl + 30 * f + size * 1.12 + 70 * f + 100 * f + 56 * f
    y0 = top + max(0, (limit - top - block) / 2) + (10 if not c.tall else 0)
    flame(c, c.W / 2, y0 + fl / 2, fl, c.fg, inner=c.pal["B"])
    y = y0 + fl + 30 * f
    c.text(c.W / 2, y, n, size, bold=True, anchor="mt")
    y += size * 1.12
    c.text(c.W / 2, y, t("shareStreakLabel", n=data["streak"]), 42 * f, bold=True, anchor="mt", alpha=0.95, maxw=c.W - 160)
    y += 100 * f
    days = i18n.get("diasSemanaCorto")
    step, r = 96 * f, 30 * f
    x0 = c.W / 2 - step * 3
    for i, (d, on) in enumerate(data["last7"]):
        x = x0 + i * step
        if on:
            c.circle(x, y, r, fill=c.fg)
            check_icon(c, x, y, r * 0.73, c.pal["B"])
        else:
            c.circle(x, y, r, outline=c.fg, width=4, alpha=0.5)
        c.text(x, y + r + 12 * f, days[d.weekday()], 22 * f, anchor="mt", alpha=0.8)
    y += r + 12 * f + 22 * f + 36 * f
    sub = f"{t('shareBest')}: {data['best']}   ·   {t('shareHoursLabel')}: {data['hours']:.0f} h"
    c.text(c.W / 2, y, sub, 30 * f, anchor="mt", alpha=0.9, maxw=c.W - 140)


def summary_card(c, data, name, message):
    top = _header(c, name)
    limit = _footer(c, message)
    m, g = 80, (1.0 if not c.tall else 1.5)
    y = top + 30 * g
    c.text(c.W / 2, y, t("shareSummary_" + data["kind"]), 56, bold=True, anchor="ma", maxw=c.W - 2 * m)
    c.text(c.W / 2, y + 74, data["label"], 30, anchor="ma", alpha=0.85)
    y += 140 * g
    items = [(t("shareHoursLabel"), _hm(data["focus_s"])), (t("shareSessions"), str(data["sessions"])),
             (t("shareActiveDays"), str(data["active_days"]))]
    if not c.tall:
        items.append((t("shareStreakShort"), str(data["streak"])))
    gap = 16
    cw = (c.W - 2 * m - gap * (len(items) - 1)) / len(items)
    th = 150
    for i, (label, val) in enumerate(items):
        x = m + i * (cw + gap)
        c.rect(x, y, x + cw, y + th, 28, fill=c.fg, alpha=0.16)
        c.text(x + cw / 2, y + th * 0.42, val, 54, bold=True, anchor="mm", maxw=cw - 24)
        c.text(x + cw / 2, y + th * 0.8, label, 22, anchor="mm", alpha=0.85, maxw=cw - 20)
    y += th + 30 * g
    extra = 0 if not c.tall else 150
    ch = max(limit - y - extra - 20, 180)
    c.rect(m, y, c.W - m, y + ch, 32, fill=c.fg, alpha=0.12)
    buckets = data["buckets"]
    topv = max([b[1] for b in buckets] + [1])
    n = max(len(buckets), 1)
    inner_w = c.W - 2 * m - 70
    bw = inner_w / n
    base = y + ch - 30
    for i, (_lab, v, _d) in enumerate(buckets):
        h = (ch - 80) * v / topv
        x = m + 35 + i * bw
        bar_w = max(bw * 0.62, 4)
        if v > 0:
            c.rect(x + (bw - bar_w) / 2, base - max(h, 8), x + (bw + bar_w) / 2, base, min(bar_w / 2, 14), fill=c.fg)
        else:
            c.rect(x + (bw - bar_w) / 2, base - 5, x + (bw + bar_w) / 2, base, 2.5, fill=c.fg, alpha=0.3)
    if c.tall:
        chips = [(t("shareStreakShort"), f"{data['streak']}")]
        if data.get("tasks_done"):
            chips.append((t("shareTasks"), str(data["tasks_done"])))
        if data.get("rate") is not None:
            chips.append((t("shareRate"), f"{data['rate']}%"))
        _chips_row(c, y + ch + 30, chips)


def achievement_card(c, data, name, message):
    top = _header(c, name)
    limit = _footer(c, message)
    f = 1.35 if c.tall else 1.0
    R = 150 * f
    title_lines = min(2, len(c.wrap(data["title"], 60 * f, c.W * 0.84, True)))
    block = R * 2.4 + 50 * f + 52 * f + title_lines * 70 * f
    y0 = top + max(0, (limit - top - block) / 2)
    cy = y0 + R * 1.2
    c.circle(c.W / 2, cy, R * 1.2, fill=c.fg, alpha=0.12)
    c.circle(c.W / 2, cy, R, fill=c.fg, alpha=0.2, outline=c.fg, width=7)
    family_icon(c, data["family"], c.W / 2, cy - R * 0.12, R * 0.62, c.fg, c.pal["B"])
    c.rect(c.W / 2 - R * 0.5, cy + R * 0.55, c.W / 2 + R * 0.5, cy + R * 1.02, 28 * f, fill=c.fg)
    c.text(c.W / 2, cy + R * 0.785, f"{data['goal']}", 46 * f, bold=True, anchor="mm", fill=c.pal["B"], maxw=R * 0.9)
    y = cy + R * 1.2 + 50 * f
    c.text(c.W / 2, y, f"{t('shareUnlocked')}  ·  {date.today().strftime('%d/%m/%Y')}", 24 * f, anchor="ma", alpha=0.8)
    c.paragraph(c.W / 2, y + 52 * f, data["title"], 60 * f, c.W * 0.84, alpha=1.0, bold=True, gap=1.15, maxlines=2)


def _hm(seconds):
    h, m = seconds // 3600, (seconds % 3600) // 60
    return f"{h}h {m:02d}m" if h else f"{m}m"


def render(kind, size, pal, data, name="", message=""):
    """kind: 'streak' | 'summary' | 'achievement'. pal: {A,B,C,FG}. Devuelve una imagen PIL RGB."""
    c = Canvas(SIZES[size], pal)
    {"streak": streak_card, "summary": summary_card, "achievement": achievement_card}[kind](c, data, name, message)
    return c.done()


def to_png_bytes(img, max_side=None):
    if max_side:
        img = img.copy()
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
