"""Motor de temas de Focus Relay (compartido en lógica con la extensión: theme-engine.js).

Un tema define 7 colores por apariencia (formato .theme versión 1):
foreground, background, highlight, highlight-foreground, secondary, surface, error.
De ahí se deriva la paleta completa de la interfaz (tarjetas, bordes, texto atenuado,
botones suaves, estados...) y se corrige cada par texto/fondo para que mantenga un
contraste legible (WCAG: 4.5:1 en texto normal), sea cual sea el tema elegido.

El tema "yopo" es la identidad original (índigo) y usa su paleta fija en ui.py.
"""
import json
import os
import re

DEFAULT_ID = "yopo"
ROLES = ("foreground", "background", "highlight", "highlight-foreground", "secondary", "surface", "error")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")

_DIR = os.path.dirname(os.path.abspath(__file__))


def _rgb(c):
    return [int(c[i:i + 2], 16) for i in (1, 3, 5)]


def mix(c1, c2, t):
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * t + 0.5) for x, y in zip(a, b))


def lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v) for v in _rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = lum(a), lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def ensure(color, bg, ratio=4.5):
    """Acerca `color` a negro/blanco (el que más contraste da con `bg`) hasta lograr `ratio`."""
    if contrast(color, bg) >= ratio:
        return color
    target = "#ffffff" if contrast("#ffffff", bg) >= contrast("#000000", bg) else "#000000"
    for i in range(1, 26):
        c = mix(color, target, i * 0.04)
        if contrast(c, bg) >= ratio:
            return c
    return target


def text_on(bgs, preferred, ratio=4.5):
    """Color de texto legible sobre uno o varios fondos; prefiere `preferred` si basta."""
    if isinstance(bgs, str):
        bgs = [bgs]
    worst = lambda c: min(contrast(c, b) for b in bgs)
    if worst(preferred) >= ratio:
        return preferred
    best = max(("#ffffff", "#0b0f19"), key=worst)
    # intenta conservar el tono del preferido acercándolo al extremo
    for i in range(1, 26):
        c = mix(preferred, best, i * 0.04)
        if worst(c) >= ratio:
            return c
    return best


def valid_theme(d):
    """Comprueba la estructura de un tema ya convertido a dict."""
    try:
        for mode in ("light", "dark"):
            for r in ROLES:
                if not _HEX.match(d[mode][r]):
                    return False
        return bool(str(d.get("name", "")).strip())
    except (KeyError, TypeError):
        return False


def parse_theme_file(text):
    """Convierte el texto de un archivo .theme (versión 1) en dict. Lanza ValueError si no es válido."""
    vals = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError("línea inválida: " + line[:40])
        k, v = line.split(":", 1)
        vals[k.strip()] = v.strip()
    if vals.get("version") != "1":
        raise ValueError("versión de tema no soportada")
    name = vals.get("name", "").strip()
    if not name:
        raise ValueError("falta el nombre")
    d = {"name": name[:40]}
    for mode in ("light", "dark"):
        d[mode] = {}
        for r in ROLES:
            v = vals.get(f"{mode}.{r}")
            if not v or not _HEX.match(v):
                raise ValueError(f"falta o es inválido {mode}.{r}")
            d[mode][r] = v[:7].lower()
    d["id"] = "custom-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    d["group"] = "custom"
    return d


def load_builtin():
    try:
        with open(os.path.join(_DIR, "themes_data.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def all_themes(custom=None):
    return load_builtin() + [c for c in (custom or []) if valid_theme(c)]


# ids antiguos (cada tema se ofrecía duplicado como «claro» y «oscuro») → tema consolidado
ALIASES = {
    "alucard-light": "dracula",
    "gruvbox-light": "gruvbox",
    "gruvbox-dark": "gruvbox",
    "nord-snow": "nord",
    "nord-polar-night": "nord",
    "solarized-light": "solarized",
    "solarized-dark": "solarized",
    "tokyo-day": "tokyo-night",
    "turquoise-light": "turquoise",
    "turquoise-dark": "turquoise"
}


def find(theme_id, custom=None):
    theme_id = ALIASES.get(theme_id, theme_id)
    for t in all_themes(custom):
        if t["id"] == theme_id:
            return t
    return None


def _far(a, b, d=70):
    return sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b))) ** 0.5 >= d


def _modes(card, hl, sec, err, success):
    """Colores de modo: Timer=highlight, Cronómetro=secondary (o verde si no se ve), Pomodoro=error."""
    t, p = hl, err
    c = sec
    if contrast(c, card) < 1.8 or not _far(c, t) or not _far(c, p):
        c = success
    if contrast(t, card) < 1.8:
        t = ensure(t, card, 1.8)
    if contrast(p, card) < 1.8:
        p = ensure(p, card, 1.8)
    return {"MODE_T": t, "MODE_C": c, "MODE_P": p}


def derive(theme, appearance):
    """Paleta completa (mismas claves que ui.LIGHT/ui.DARK) para un tema y una apariencia."""
    p = theme[appearance]
    dark = appearance == "dark"
    fg, bg, hl, hlfg = p["foreground"], p["background"], p["highlight"], p["highlight-foreground"]
    sec, surf, err = p["secondary"], p["surface"], p["error"]

    if dark:
        canvas, card = bg, mix(bg, surf, 0.55)
    else:
        canvas, card = mix(bg, surf, 0.5), mix(bg, "#ffffff", 0.5)
    for i in range(6):          # tarjeta y fondo deben distinguirse
        if contrast(card, canvas) >= 1.06:
            break
        card = mix(card, "#ffffff" if dark else surf, 0.12) if dark else mix(card, "#ffffff", 0.35)
    ink = ensure(fg, card, 7.0)
    ink = ensure(ink, canvas, 7.0)
    line = mix(card, ink, 0.16 if dark else 0.14)
    muted = ensure(ensure(mix(ink, card, 0.36), card, 4.5), canvas, 4.5)
    primary = hl
    on_primary = text_on(primary, hlfg)
    primary_2 = mix(hl, sec, 0.55)
    hero_a, hero_b, hero_c = mix(hl, bg, 0.22), hl, primary_2
    hero_fg = text_on([hero_a, hero_b, hero_c], hlfg)
    if all(_HEX.match(str(p.get(k, ""))) for k in ("hero-start", "hero-mid", "hero-end")):
        # el tema fija su propio degradado del encabezado (p. ej. Rosa claro, para tener letras blancas)
        hero_a, hero_b, hero_c = (p[k][:7] for k in ("hero-start", "hero-mid", "hero-end"))
        if _HEX.match(str(p.get("hero-foreground", ""))):
            hero_fg = p["hero-foreground"][:7]
    for i in range(1, 21):      # si no alcanza el contraste, se aclara/oscurece el degradado
        if min(contrast(hero_fg, c) for c in (hero_a, hero_b, hero_c)) >= 4.5:
            break
        away = "#000000" if lum(hero_fg) > 0.4 else "#ffffff"
        hero_a, hero_b, hero_c = (mix(c, away, 0.04 * i) for c in (hero_a, hero_b, hero_c))

    ghost_bg = mix(card, hl, 0.2 if dark else 0.13)
    ghost_hover = mix(card, hl, 0.30 if dark else 0.22)
    accent = ensure(hl, ghost_hover, 4.5)
    accent = ensure(accent, card, 4.5)

    success = ensure("#19b394" if dark else "#0f9d83", card, 3.0)
    success_bg = mix(card, success, 0.16 if dark else 0.12)
    success_fg = ensure(success, success_bg, 4.5)
    danger_bg = mix(card, err, 0.2 if dark else 0.12)
    danger_hover = mix(card, err, 0.3 if dark else 0.2)
    danger = ensure(err, danger_hover, 4.5)

    field = mix(canvas, card, 0.3) if dark else mix(card, canvas, 0.25)
    soft = mix(canvas, card, 0.5) if dark else mix(card, canvas, 0.45)
    return {
        "INK": ink, "MUTED": muted, "SURFACE": card, "CANVAS": canvas,
        "LINE": line, "PRIMARY": primary, "PRIMARY_2": primary_2, "ACCENT": accent,
        "HERO_A": hero_a, "HERO_B": hero_b, "HERO_C": hero_c, "HERO_FG": hero_fg,
        "ON_PRIMARY": on_primary,
        "GHOST_BG": ghost_bg, "GHOST_HOVER": ghost_hover,
        "SUCCESS": success, "SUCCESS_BG": success_bg, "SUCCESS_FG": success_fg,
        "DANGER": danger, "DANGER_BG": danger_bg, "DANGER_HOVER": danger_hover,
        "FIELD_BG": field, "SOFT": soft, "TAG_BG": mix(card, ink, 0.07),
        "DOT_OFF": mix(muted, card, 0.35),
        "SELECT_BG": mix(card, hl, 0.1 if dark else 0.07),
        "CTRL_BORDER": ensure(mix(card, ink, 0.4), card, 3.0),
        "SCROLL": mix(card, ink, 0.2), "SCROLL_HOT": mix(card, ink, 0.34),
        # colores de modo por defecto (Timer, Cronómetro, Pomodoro)
        **_modes(card, hl, sec, err, success),
    }


def mode_colors(theme, appearance):
    d = derive(theme, appearance)
    return {"T": d["MODE_T"], "C": d["MODE_C"], "P": d["MODE_P"]}
