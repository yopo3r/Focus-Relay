"""Sistema visual de Focus Relay Desktop.

Comparte identidad con la extensión del navegador y la página del ESP-01S:
los valores de color, radios y jerarquía salen del style.css de la extensión
(índigo/violeta, tarjetas blancas sobre fondo azulado, encabezado en degradado).

Tkinter no tiene esquinas redondeadas ni degradados, así que los botones,
tarjetas, pills y el encabezado se dibujan sobre Canvas. Los campos de texto,
casillas y barras de desplazamiento usan ttk con el tema "clam" restilizado.
"""
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# --- Paleta (tomada de la extensión Focus Relay; misma en web, extensión y escritorio) ---
LIGHT = {
    "INK": "#162033", "MUTED": "#687386", "SURFACE": "#ffffff", "CANVAS": "#f2f5fa",
    "LINE": "#dfe5ef", "PRIMARY": "#5b5bd6", "PRIMARY_2": "#7767e8", "ACCENT": "#5b5bd6",
    "HERO_A": "#252d57", "HERO_C": "#7b61d9", "GHOST_BG": "#eef0ff", "GHOST_HOVER": "#e0e3ff",
    "SUCCESS": "#0f9d83", "SUCCESS_BG": "#eef7f5", "SUCCESS_FG": "#187160",
    "DANGER": "#c8435c", "DANGER_BG": "#fff0f3", "DANGER_HOVER": "#ffe0e7",
    "FIELD_BG": "#fbfcfe", "SOFT": "#f8fafc", "TAG_BG": "#f0f2f7", "DOT_OFF": "#9aa4b3",
    "SELECT_BG": "#f4f4ff", "CTRL_BORDER": "#aeb8cc", "SCROLL": "#cfd6e4", "SCROLL_HOT": "#aeb8cc",
    "HERO_B": "#5b5bd6", "HERO_FG": "#ffffff", "ON_PRIMARY": "#ffffff",
    "MODE_T": "#5b5bd6", "MODE_C": "#059669", "MODE_P": "#dc2626",
}
DARK = {
    "INK": "#e8ecf6", "MUTED": "#9aa6bb", "SURFACE": "#171d2e", "CANVAS": "#0e1320",
    "LINE": "#2b3450", "PRIMARY": "#5b5bd6", "PRIMARY_2": "#7767e8", "ACCENT": "#aeb0ff",
    "HERO_A": "#161b38", "HERO_C": "#6a55c9", "GHOST_BG": "#262b57", "GHOST_HOVER": "#30366b",
    "SUCCESS": "#19b394", "SUCCESS_BG": "#12332f", "SUCCESS_FG": "#5fd6bd",
    "DANGER": "#f0708a", "DANGER_BG": "#3a1d29", "DANGER_HOVER": "#4a2434",
    "FIELD_BG": "#111729", "SOFT": "#131a2b", "TAG_BG": "#232b40", "DOT_OFF": "#6b7690",
    "SELECT_BG": "#20264a", "CTRL_BORDER": "#55607c", "SCROLL": "#38425e", "SCROLL_HOT": "#55607c",
    "HERO_B": "#5b5bd6", "HERO_FG": "#ffffff", "ON_PRIMARY": "#ffffff",
    "MODE_T": "#5b5bd6", "MODE_C": "#059669", "MODE_P": "#dc2626",
}
globals().update(LIGHT)
THEME = "light"          # tema efectivo en uso ("light" | "dark")
WHITE = "#ffffff"


def mix(c1, c2, t):
    """Mezcla dos colores #rrggbb: t=0 -> c1, t=1 -> c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def lum(c):
    import themes
    return themes.lum(c)


def mode_color(code, override=None):
    """Color del modo T/C/P: el elegido por el usuario o el del tema activo."""
    if override and override.get(code) and not _is_old_default(override, code):
        return override[code]
    return globals()["MODE_" + ("P" if code == "P" else code)]


_OLD_DEFAULTS = {"T": "#5b5bd6", "C": "#059669", "P": "#dc2626"}


def _is_old_default(override, code):
    # Los valores que traía la app por defecto cuentan como "automático" al usar otro tema.
    return PALETTE != "yopo" and override[code].lower() == _OLD_DEFAULTS[code]


def _readable(color, bg, ratio=4.5):
    import themes
    return themes.ensure(color, bg, ratio)


def on_color(bg, preferred="#ffffff"):
    """Texto legible sobre un color de fondo arbitrario."""
    import themes
    return themes.text_on(bg, preferred, 4.5)


PRIMARY_HOVER = mix(PRIMARY, "#ffffff", 0.08)   # el CSS usa brightness(1.06)

THEME_CHOICES = [("light", "Claro"), ("dark", "Oscuro"), ("system", "Sistema")]


def detect_system_theme():
    """'dark' o 'light' según el sistema operativo (claro si no se puede saber)."""
    import os
    import platform
    import subprocess
    system = platform.system()
    try:
        if system == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            return "light" if winreg.QueryValueEx(key, "AppsUseLightTheme")[0] else "dark"
        if system == "Darwin":
            out = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                                 capture_output=True, text=True, timeout=2)
            return "dark" if "dark" in out.stdout.lower() else "light"
        gtk = os.environ.get("GTK_THEME", "")
        if gtk:
            return "dark" if "dark" in gtk.lower() else "light"
        for key in ("color-scheme", "gtk-theme"):
            out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", key],
                                 capture_output=True, text=True, timeout=2, env=__import__("config").system_env())
            val = out.stdout.lower()
            if out.returncode == 0 and ("dark" in val):
                return "dark"
            if key == "color-scheme" and "default" in val and out.returncode == 0:
                continue
    except Exception:
        pass
    return "light"


PALETTE = "yopo"         # id del tema de color en uso ("yopo" = identidad original)


def apply_theme(choice, palette_id="yopo", custom=None):
    """Aplica apariencia 'light' | 'dark' | 'system' y tema de color. True si cambió algo.

    Los widgets ya creados conservan sus colores: quien cambie el tema debe
    reconstruir las ventanas abiertas.
    """
    global THEME, PRIMARY_HOVER, PALETTE
    import themes
    effective = detect_system_theme() if choice == "system" else ("dark" if choice == "dark" else "light")
    th = None if palette_id in (None, "", themes.DEFAULT_ID) else themes.find(palette_id, custom)
    pid = th["id"] if th else themes.DEFAULT_ID
    changed = effective != THEME or pid != PALETTE
    THEME, PALETTE = effective, pid
    base = DARK if effective == "dark" else LIGHT
    globals().update(themes.derive(th, effective) if th else base)
    PRIMARY_HOVER = mix(PRIMARY, "#ffffff" if lum(PRIMARY) < 0.5 else "#000000", 0.08)
    _state["ready"].clear()      # fuerza a reconfigurar los estilos ttk con la nueva paleta
    _state["styles"].clear()
    return changed


TEXT_SCALE = 1.0


def apply_text_scale(root, factor):
    """Escala todas las fuentes de la app (F() multiplica los tamaños). Reconstruir las ventanas después."""
    global TEXT_SCALE
    try:
        TEXT_SCALE = min(1.6, max(0.8, float(factor)))
    except (TypeError, ValueError):
        TEXT_SCALE = 1.0
    _state["ready"].clear()


def scaled(n):
    """Escala una medida en píxeles (tamaños de ventana, etc.) con el mismo factor que los textos."""
    return int(round(n * max(1.0, TEXT_SCALE)))


def refresh_theme():
    """Lee la preferencia guardada en config.json y la aplica."""
    from config import load_config
    cfg = load_config()
    return apply_theme(cfg.get("theme", "system"), cfg.get("palette", "yopo"), cfg.get("custom_themes"))


_FAMILY_CANDIDATES = ["Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Roboto",
                      "Noto Sans", "Ubuntu", "Cantarell", "DejaVu Sans", "Arial"]
_state = {"family": None, "ready": set(), "styles": set()}


def _family(root):
    if _state["family"] is None:
        have = set(tkfont.families(root))
        _state["family"] = next((f for f in _FAMILY_CANDIDATES if f in have), "TkDefaultFont")
    return _state["family"]


def F(kind="body"):
    """Fuente por rol. Requiere haber llamado a ensure() antes."""
    fam = _state["family"] or "TkDefaultFont"
    base = {
        "body": (fam, 10),
        "bold": (fam, 10, "bold"),
        "small": (fam, 9),
        "small_bold": (fam, 9, "bold"),
        "tiny": (fam, 8),
        "eyebrow": (fam, 8, "bold"),
        "h1": (fam, 15, "bold"),
        "h2": (fam, 11, "bold"),
        "time": (fam, 12, "bold"),
        "clock": (fam, 40, "bold"),
        "quote": (fam, 19, "bold"),
    }[kind]
    size = base[1] * TEXT_SCALE
    if kind == "clock":                      # el reloj vive dentro de un anillo de tamaño fijo
        size = base[1] * min(TEXT_SCALE, 1.0)
    return (base[0], max(6, int(round(size)))) + tuple(base[2:])


def ensure(widget):
    """Prepara fuentes y estilos ttk una sola vez por aplicación."""
    root = widget._root()
    if id(root) in _state["ready"]:
        return
    _state["ready"].add(id(root))
    _family(root)                               # fija la familia tipográfica que usa F()
    root.option_add("*Font", F("body"))
    root.option_add("*TCombobox*Listbox.font", F("body"))
    root.option_add("*TCombobox*Listbox.background", SURFACE)
    root.option_add("*TCombobox*Listbox.foreground", INK)
    root.option_add("*TCombobox*Listbox.selectBackground", GHOST_BG)
    root.option_add("*TCombobox*Listbox.selectForeground", ACCENT)

    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass
    for name in ("App.TEntry", "App.TSpinbox", "App.TCombobox"):
        s.configure(name, fieldbackground=FIELD_BG, foreground=INK, bordercolor=LINE,
                    lightcolor=LINE, darkcolor=LINE, insertcolor=INK, padding=(8, 6),
                    arrowcolor=MUTED, arrowsize=14, background=SURFACE, selectbackground=GHOST_BG,
                    selectforeground=INK)
        s.map(name, bordercolor=[("focus", PRIMARY)], lightcolor=[("focus", PRIMARY)],
              darkcolor=[("focus", PRIMARY)], fieldbackground=[("disabled", TAG_BG)])
    s.configure("App.TCombobox", padding=(8, 6))
    s.map("App.TCombobox", fieldbackground=[("readonly", FIELD_BG)],
          foreground=[("readonly", INK)], selectbackground=[("readonly", FIELD_BG)],
          selectforeground=[("readonly", INK)])
    # Barra de desplazamiento fina y sin flechas, como en la web.
    s.layout("App.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {
        "sticky": "ns", "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    s.configure("App.Vertical.TScrollbar", troughcolor=SURFACE, background=SCROLL,
                bordercolor=SURFACE, lightcolor=SCROLL, darkcolor=SCROLL, gripcount=0, width=8)
    s.map("App.Vertical.TScrollbar", background=[("active", SCROLL_HOT)],
          lightcolor=[("active", SCROLL_HOT)], darkcolor=[("active", SCROLL_HOT)])
    s.configure("App.TSeparator", background=LINE)
    s.configure("App.Horizontal.TScale", background=PRIMARY, troughcolor=LINE, bordercolor=SURFACE,
                lightcolor=PRIMARY, darkcolor=PRIMARY, sliderthickness=16, sliderrelief="flat")
    s.map("App.Horizontal.TScale", background=[("active", PRIMARY_HOVER)],
          lightcolor=[("active", PRIMARY_HOVER)], darkcolor=[("active", PRIMARY_HOVER)])


def _style_for(kind, bg):
    """Estilo ttk de casillas/opciones con el fondo de su contenedor."""
    ensure_name = f"{bg[1:]}.App.T{kind}"
    if ensure_name not in _state["styles"]:
        s = ttk.Style()
        s.configure(ensure_name, background=bg, foreground=INK, font=F("body"),
                    focuscolor=bg, indicatorbackground=FIELD_BG, indicatorforeground=PRIMARY,
                    indicatorcolor=FIELD_BG, bordercolor=CTRL_BORDER, lightcolor=CTRL_BORDER,
                    darkcolor=CTRL_BORDER, upperbordercolor=CTRL_BORDER, lowerbordercolor=CTRL_BORDER,
                    padding=(2, 3))
        s.map(ensure_name, background=[("active", bg)],
              indicatorcolor=[("selected", PRIMARY), ("pressed", GHOST_BG)],
              indicatorbackground=[("selected", PRIMARY)],
              indicatorforeground=[("selected", ON_PRIMARY)],
              bordercolor=[("selected", PRIMARY)], upperbordercolor=[("selected", PRIMARY)],
              lowerbordercolor=[("selected", PRIMARY)])
        _state["styles"].add(ensure_name)
    return ensure_name


# --- Dibujo -----------------------------------------------------------------
def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


# --- Widgets ----------------------------------------------------------------
class Button(tk.Canvas):
    """Botón redondeado: primary (sólido), ghost (tenue) o danger (rosado)."""

    @staticmethod
    def _styles():
        return {
            "primary": (PRIMARY, PRIMARY_HOVER, ON_PRIMARY, None),
            "ghost": (GHOST_BG, GHOST_HOVER, ACCENT, None),
            "danger": (DANGER_BG, DANGER_HOVER, DANGER, None),
            "plain": (SURFACE, SOFT, INK, LINE),
        }

    def __init__(self, parent, text, command=None, style="primary", padx=16, pady=9,
                 radius=11, font=None):
        ensure(parent)
        bg = parent.cget("bg") if "bg" in parent.keys() else CANVAS
        self._font = font or F("bold")
        self._pbg = bg
        self._text, self._command, self._style = text, command, style
        self._padx, self._pady, self._radius = padx, pady, radius
        self._state, self._hover = "normal", False
        self._accent = None
        f = tkfont.Font(font=self._font)
        w = f.measure(text) + 2 * padx
        h = f.metrics("linespace") + 2 * pady
        super().__init__(parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self._measure = f
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", lambda e: self.invoke())
        self.bind("<space>", lambda e: self.invoke())
        self.bind("<FocusIn>", lambda e: self._draw())
        self.bind("<FocusOut>", lambda e: self._draw())
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def set_accent(self, color):
        """Color propio (modo activo) para los estilos primary / ghost."""
        self._accent = color
        self._draw()

    def set_bg(self, color):
        """Cambia el color del fondo sobre el que se apoya (para botones translúcidos)."""
        self._pbg = color
        self.config(bg=color)
        self._draw()

    def _set_hover(self, on):
        self._hover = on
        self._draw()

    def _release(self, event):
        if self._state == "normal" and 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.invoke()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            w, h = int(self["width"]), int(self["height"])
        if self._style == "glass":            # translúcido sobre un fondo de color (tarjeta del reloj)
            on = on_color(self._pbg)
            base, hover, fg = mix(self._pbg, on, .16), mix(self._pbg, on, .27), on
            border = mix(self._pbg, on, .55)
        elif self._style == "glass_on":       # opción activa sobre el fondo de color
            on = on_color(self._pbg)
            base, hover, fg, border = on, on, self._pbg, None
        else:
            base, hover, fg, border = self._styles()[self._style]
            if self._accent and self._style == "primary":        # botón sólido del color del modo
                on = on_color(self._accent)
                base, hover, fg = self._accent, mix(self._accent, on, .1), on
            elif self._accent and self._style == "ghost":        # botón tenue teñido con el modo
                base = mix(SURFACE, self._accent, .12)
                hover = mix(SURFACE, self._accent, .2)
                fg = _readable(self._accent, base)
        fill = hover if (self._hover and self._state == "normal") else base
        if self._state == "disabled":
            fill, fg, border = TAG_BG, DOT_OFF, None
        round_rect(self, 1, 1, w - 1, h - 1, self._radius, fill=fill,
                   outline=border or fill, width=1)
        if self.focus_get() is self and self._state == "normal":
            round_rect(self, 2, 2, w - 2, h - 2, self._radius, fill="", outline=PRIMARY_2, width=1)
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font)

    def invoke(self):
        if self._state == "normal" and self._command:
            self._command()

    def configure(self, cnf=None, **kw):
        cnf = dict(cnf or {}, **kw)
        redraw = False
        if "state" in cnf:
            self._state = cnf.pop("state")
            self.config(cursor="hand2" if self._state == "normal" else "arrow")
            redraw = True
        if "text" in cnf:
            self._text = cnf.pop("text")
            self.config(width=self._measure.measure(self._text) + 2 * self._padx)
            redraw = True
        if "command" in cnf:
            self._command = cnf.pop("command")
        if cnf:
            super().configure(cnf)
        if redraw:
            self._draw()

    config = configure

    @property
    def text(self):
        return self._text


class Pill(tk.Canvas):
    """Etiqueta redondeada pequeña (tipo de sesión, duración, estado)."""

    def __init__(self, parent, text, fg=None, bg=None, dot=None, font=None):
        ensure(parent)
        fg, bg = fg or ACCENT, bg or GHOST_BG
        pbg = parent.cget("bg") if "bg" in parent.keys() else CANVAS
        font = font or F("small_bold")
        f = tkfont.Font(font=font)
        dot_w = 14 if dot else 0
        w = f.measure(text) + 20 + dot_w
        h = f.metrics("linespace") + 8
        super().__init__(parent, width=w, height=h, bg=pbg, highlightthickness=0, bd=0)
        round_rect(self, 0, 0, w, h, h / 2, fill=bg, outline=bg)
        x = 10
        if dot:
            self.create_oval(x + 5 - 7, h / 2 - 7, x + 5 + 7, h / 2 + 7, fill=mix(dot, bg, 0.82), outline="")
            self.create_oval(x + 1, h / 2 - 4, x + 9, h / 2 + 4, fill=dot, outline="")
            x += 14
        self.create_text(x, h / 2, text=text, fill=fg, font=font, anchor="w")


class Card(tk.Canvas):
    """Tarjeta blanca de esquinas redondeadas y borde fino. El contenido va en `.body`."""

    def __init__(self, parent, fill=None, radius=16, pad=16, expand=False, border=None):
        ensure(parent)
        fill, border = fill or SURFACE, border or LINE
        pbg = parent.cget("bg") if "bg" in parent.keys() else CANVAS
        super().__init__(parent, bg=pbg, highlightthickness=0, bd=0, height=40)
        self._fill, self._radius, self._pad, self._expand, self._border = fill, radius, pad, expand, border
        self.body = tk.Frame(self, bg=fill)
        self._win = self.create_window(pad, pad, anchor="nw", window=self.body)
        self.bind("<Configure>", self._on_canvas)
        self.body.bind("<Configure>", self._on_body)

    def recolor(self, fill, border=None):
        self._fill, self._border = fill, border or fill
        self.body.configure(bg=fill)
        self._redraw()

    def _redraw(self):
        self.delete("bg")
        w, h = self.winfo_width(), self.winfo_height()
        if w > 4 and h > 4:
            round_rect(self, 1, 1, w - 1, h - 1, self._radius, fill=self._fill,
                       outline=self._border, width=1, tags="bg")
            self.tag_lower("bg")

    def _on_canvas(self, e):
        opts = {"width": max(1, e.width - 2 * self._pad)}
        if self._expand:
            opts["height"] = max(1, e.height - 2 * self._pad)
        self.itemconfigure(self._win, **opts)
        self._redraw()

    def _on_body(self, e):
        if not self._expand:
            want = e.height + 2 * self._pad
            if int(self["height"]) != want:
                self.configure(height=want)


_logo_cache = {}


def logo_photo(size, a, b, fg):
    """Logo de la app como imagen de Tk (None si falta Pillow/ImageTk). Se guarda en caché por tamaño y colores."""
    key = (size, a, b, fg)
    if key not in _logo_cache:
        try:
            from PIL import ImageTk
            import icon_art
            _logo_cache[key] = ImageTk.PhotoImage(icon_art.draw(scaled(size), a, b, fg))
        except Exception:
            _logo_cache[key] = None
    return _logo_cache[key]


class Hero(tk.Canvas):
    """Encabezado con degradado (#252d57 → #5b5bd6 → #7b61d9), marca y estado."""

    def __init__(self, parent, title, eyebrow="FOCUS RELAY", height=84):
        ensure(parent)
        super().__init__(parent, height=height, highlightthickness=0, bd=0, bg=HERO_A)
        self._title, self._eyebrow, self._h = title, eyebrow, height
        self._status = ("", None)
        self._gw = 0
        self.bind("<Configure>", self._draw)

    def set_title(self, title):
        self._title = title
        self._draw(force=True)

    def set_status(self, text, online=None):
        """online: True (verde), False (gris) o None (sin punto)."""
        if getattr(self, "_status", None) == (text, online):
            return                        # no repintar el degradado si nada cambió
        self._status = (text, online)
        self._draw(force=True)

    @staticmethod
    def _grad(t):
        return mix(HERO_A, HERO_B, t / 0.62) if t < 0.62 else mix(HERO_B, HERO_C, (t - 0.62) / 0.38)

    def _draw(self, event=None, force=False):
        w = event.width if event is not None else self.winfo_width()
        if w < 10:
            return
        h = self._h
        if w != self._gw or force:
            self.delete("all")
            step = 3
            for x in range(0, w, step):
                self.create_rectangle(x, 0, x + step, h, fill=self._grad(x / w), outline="")
            # marca: el logo de la aplicación (mismo dibujo que el ícono de la app y de la bandeja)
            mx, my, ms = 20, (h - 40) / 2, 40
            photo = logo_photo(ms, mix(HERO_A, HERO_FG, 0.10), mix(HERO_C, HERO_FG, 0.10), HERO_FG)
            if photo is not None:
                self._logo = photo                                  # referencia para que Tk no la libere
                self.create_image(mx + ms / 2, my + ms / 2, image=photo)    # sin marco extra: el ícono ya trae sus bordes
            else:                                                   # sin Pillow/ImageTk: reloj sencillo
                round_rect(self, mx, my, mx + ms, my + ms, 13, fill=mix(self._grad(0.05), HERO_FG, 0.16), outline="")
                cx, cy = mx + ms / 2, my + ms / 2
                self.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, outline=HERO_FG, width=2)
                self.create_line(cx, cy, cx, cy - 6, fill=HERO_FG, width=2, capstyle="round")
                self.create_line(cx, cy, cx + 5, cy + 3, fill=HERO_FG, width=2, capstyle="round")
            self.create_text(mx + ms + 14, h / 2 - 12, text=self._eyebrow.upper(), anchor="w",
                             fill=mix(self._grad(0.3), HERO_FG, 0.82), font=F("eyebrow"))
            self.create_text(mx + ms + 14, h / 2 + 8, text=self._title, anchor="w",
                             fill=HERO_FG, font=F("h1"))
            text, online = self._status
            if text:
                f = tkfont.Font(font=F("small_bold"))
                pw = f.measure(text) + 24 + (16 if online is not None else 0)
                ph = 28
                px2, py = w - 20, h / 2
                bgc = mix(self._grad(0.9), HERO_FG, 0.16)
                round_rect(self, px2 - pw, py - ph / 2, px2, py + ph / 2, ph / 2, fill=bgc, outline="")
                x = px2 - pw + 12
                if online is not None:
                    col = SUCCESS if online else DOT_OFF
                    if online:
                        self.create_oval(x - 3, py - 8, x + 13, py + 8, fill=mix(col, bgc, 0.7), outline="")
                    self.create_oval(x + 1, py - 4, x + 9, py + 4, fill=col if online else "#c6cdda", outline="")
                    x += 16
                self.create_text(x, py, text=text, anchor="w", fill=HERO_FG, font=F("small_bold"))
            self._gw = w


class Segmented(tk.Canvas):
    """Selector de 2-3 opciones tipo píldora (Claro / Oscuro / Sistema). `command(key)` al elegir."""

    def __init__(self, parent, choices, value, command=None, padx=16, pady=7):
        ensure(parent)
        pbg = parent.cget("bg") if "bg" in parent.keys() else CANVAS
        self._choices, self._value, self._command = list(choices), value, command
        self._accent = None
        self._font = F("small_bold")
        f = tkfont.Font(font=self._font)
        self._ws = [f.measure(label) + 2 * padx for _k, label in self._choices]
        self._h = f.metrics("linespace") + 2 * pady
        super().__init__(parent, width=sum(self._ws) + 8, height=self._h + 8, bg=pbg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.bind("<Button-1>", self._click)
        self._draw()

    @property
    def value(self):
        return self._value

    def set_accent(self, color):
        self._accent = color
        self._draw()

    def set(self, value):
        self._value = value
        self._draw()

    def _click(self, e):
        x = 4
        for (key, _label), w in zip(self._choices, self._ws):
            if x <= e.x < x + w:
                if key != self._value:
                    self._value = key
                    self._draw()
                    if self._command:
                        self._command(key)
                return
            x += w

    def _draw(self):
        self.delete("all")
        total = sum(self._ws) + 8
        round_rect(self, 0, 0, total, self._h + 8, (self._h + 8) / 2, fill=TAG_BG, outline=LINE)
        x = 4
        for (key, label), w in zip(self._choices, self._ws):
            sel = key == self._value
            if sel:
                col = self._accent or PRIMARY
                round_rect(self, x, 4, x + w, 4 + self._h, self._h / 2, fill=col, outline=col)
            self.create_text(x + w / 2, 4 + self._h / 2, text=label, font=self._font,
                             fill=(on_color(self._accent) if self._accent else ON_PRIMARY) if sel else MUTED)
            x += w


class Notice(tk.Canvas):
    """Aviso redondeado (éxito / info / error). Vacío = se oculta."""

    @staticmethod
    def _kinds():
        return {"success": (SUCCESS_BG, SUCCESS_FG), "info": (GHOST_BG, ACCENT),
                "error": (DANGER_BG, DANGER), "soft": (SOFT, MUTED)}

    def __init__(self, parent, kind="success"):
        ensure(parent)
        pbg = parent.cget("bg") if "bg" in parent.keys() else CANVAS
        super().__init__(parent, bg=pbg, highlightthickness=0, bd=0, height=1)
        self._kind, self._text = kind, ""
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, text, kind=None):
        self._text = text or ""
        if kind:
            self._kind = kind
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        if not self._text or w < 20:
            self.configure(height=1)
            return
        bg, fg = self._kinds()[self._kind]
        t = self.create_text(14, 10, text=self._text, anchor="nw", fill=fg, font=F("small_bold"), width=w - 28)
        x1, y1, x2, y2 = self.bbox(t)
        h = (y2 - y1) + 20
        if int(self["height"]) != h:
            self.configure(height=h)
        round_rect(self, 0, 0, w, h, 11, fill=bg, outline=bg)
        self.tag_raise(t)


# --- Fábricas de widgets ttk / tk con el estilo de la app ----------------------
def label(parent, text="", kind="body", bg=None, **kw):
    bg = bg or (parent.cget("bg") if "bg" in parent.keys() else CANVAS)
    fg = {"body": INK, "bold": INK, "muted": MUTED, "title": INK, "eyebrow": MUTED, "error": DANGER}[kind]
    font = {"body": "body", "bold": "bold", "muted": "small", "title": "h2", "eyebrow": "eyebrow", "error": "small_bold"}[kind]
    if kind == "eyebrow":
        text = text.upper()
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=F(font), anchor="w", justify="left", **kw)


def entry(parent, textvariable=None, width=None, show=None):
    ensure(parent)
    kw = {"textvariable": textvariable, "style": "App.TEntry", "font": F("body")}
    if width:
        kw["width"] = width
    if show is not None:
        kw["show"] = show
    return ttk.Entry(parent, **kw)


def spinbox(parent, textvariable, lo, hi, width=5, increment=1):
    ensure(parent)
    return ttk.Spinbox(parent, from_=lo, to=hi, increment=increment, textvariable=textvariable,
                       width=width, style="App.TSpinbox", font=F("body"))


def combobox(parent, textvariable, values):
    ensure(parent)
    return ttk.Combobox(parent, textvariable=textvariable, values=values, state="readonly",
                        style="App.TCombobox", font=F("body"))


def checkbutton(parent, text, variable, command=None, bg=None):
    ensure(parent)
    bg = bg or SURFACE
    return ttk.Checkbutton(parent, text=text, variable=variable, command=command,
                           style=_style_for("Checkbutton", bg))


def radiobutton(parent, text, variable, value, bg=None, command=None):
    ensure(parent)
    bg = bg or SURFACE
    return ttk.Radiobutton(parent, text=text, variable=variable, value=value, command=command,
                           style=_style_for("Radiobutton", bg))


def scrollbar(parent, command):
    ensure(parent)
    return ttk.Scrollbar(parent, orient="vertical", command=command, style="App.Vertical.TScrollbar")


class ScrollList(tk.Frame):
    """Lista con borde fino, margen interno y barra de desplazamiento que solo aparece si hace falta."""

    def __init__(self, parent, height=6, selectmode="extended"):
        ensure(parent)
        super().__init__(parent, bg=FIELD_BG, highlightthickness=1, highlightbackground=LINE,
                         highlightcolor=PRIMARY, bd=0)
        self.listbox = tk.Listbox(self, font=F("body"), height=height, selectmode=selectmode,
                                  activestyle="none", bg=FIELD_BG, fg=INK, relief="flat", bd=0,
                                  highlightthickness=0, selectbackground=GHOST_BG,
                                  selectforeground=ACCENT, selectborderwidth=0, exportselection=False)
        self._sb = scrollbar(self, self.listbox.yview)
        self.listbox.configure(yscrollcommand=self._on_scroll)
        self.listbox.pack(side="left", fill="both", expand=True, padx=(10, 2), pady=6)

    def _on_scroll(self, first, last):
        self._sb.set(first, last)
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._sb.pack_forget()
        elif not self._sb.winfo_ismapped():
            self._sb.pack(side="right", fill="y", padx=(0, 3), pady=4)


def wheel_over(frame, e):
    """¿Está el puntero sobre `frame` (o un descendiente suyo)? Así la rueda/trackpad funciona sobre cualquier hijo,
    sin depender de eventos Enter/Leave (que se pierden al pasar a un widget interior)."""
    if getattr(frame, "_gone", False):
        return False
    try:
        w = frame.winfo_containing(e.x_root, e.y_root)
    except (tk.TclError, KeyError):
        return False
    while w is not None:
        if w is frame:
            return True
        w = getattr(w, "master", None)
    return False


def wheel_units(frame, e, per_notch=3):
    """Convierte un evento de rueda en líneas enteras. Los trackpads de precisión de Windows envían deltas pequeños
    (p. ej. 8–30 en vez de 120): se acumulan para que no se redondeen a cero."""
    num = getattr(e, "num", None)
    if num == 4:
        return -per_notch
    if num == 5:
        return per_notch
    d = getattr(e, "delta", 0) or 0
    if sys.platform == "darwin":
        frame._wacc = getattr(frame, "_wacc", 0.0) - d
    else:
        frame._wacc = getattr(frame, "_wacc", 0.0) - d / 120.0 * per_notch
    n = int(frame._wacc)
    frame._wacc -= n
    return n


_NO_PAN = ("Entry", "Text", "Scale", "Scrollbar", "Listbox", "TScrollbar", "TScale", "TCombobox", "TEntry", "Spinbox",
           "TSpinbox", "Combobox")


def enable_touch_scroll(frame, canvas, can_scroll=None):
    """Desplazamiento por gesto para pantallas táctiles y trackpads que no envían rueda (Tk en Windows): arrastrar con
    el dedo sobre el área desplaza el contenido (umbral de 8 px para no estorbar a los clics); además atiende
    <TouchpadScroll> (Tk 8.7/9) y las teclas RePág/AvPág."""
    st = {"y": None, "drag": False, "acc": 0.0}

    def inside(e):
        return wheel_over(frame, e)

    def press(e):
        st["y"], st["drag"] = None, False
        if inside(e) and e.widget.winfo_class() not in _NO_PAN and (can_scroll is None or can_scroll()):
            st["y"] = e.y_root

    def motion(e):
        if st["y"] is None:
            return
        dy = e.y_root - st["y"]
        if not st["drag"] and abs(dy) < 8:
            return
        st["drag"] = True
        st["y"] = e.y_root
        st["acc"] -= dy / 18.0                                   # ~18 px por línea
        n = int(st["acc"])
        if n:
            st["acc"] -= n
            canvas.yview_scroll(n, "units")

    def release(e):
        st["y"] = None

    def touchpad(e):
        if not inside(e) or (can_scroll is not None and not can_scroll()):
            return
        try:
            _dx, dy = (float(v) for v in frame.tk.call("tk::PreciseScrollDeltas", e.delta).split())
        except Exception:
            return
        st["acc"] -= dy / 18.0
        n = int(st["acc"])
        if n:
            st["acc"] -= n
            canvas.yview_scroll(n, "units")

    def key(e):
        if not inside(e) or e.widget.winfo_class() in _NO_PAN or (can_scroll is not None and not can_scroll()):
            return
        if e.keysym == "Prior":
            canvas.yview_scroll(-1, "pages")
        elif e.keysym == "Next":
            canvas.yview_scroll(1, "pages")

    for ev, fn in (("<ButtonPress-1>", press), ("<B1-Motion>", motion), ("<ButtonRelease-1>", release),
                   ("<Prior>", key), ("<Next>", key)):
        frame.bind_all(ev, fn, add="+")
    try:
        frame.bind_all("<TouchpadScroll>", touchpad, add="+")
    except tk.TclError:
        pass                                                    # Tk 8.6 no conoce ese evento


class ScrollFrame(tk.Frame):
    """Contenedor con desplazamiento vertical (rueda del mouse incluida). El contenido va en `.inner`."""

    def __init__(self, parent, bg=None):
        ensure(parent)
        bg = bg or CANVAS
        super().__init__(parent, bg=bg)
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._sb = scrollbar(self, self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._on_scroll)
        self._canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self._canvas, bg=bg)
        self._win = self._canvas.create_window(0, 0, anchor="nw", window=self.inner)
        self.inner.bind("<Configure>", lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfigure(self._win, width=e.width))
        self._gone = False
        self.bind("<Destroy>", lambda e: setattr(self, "_gone", True) if e.widget is self else None)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>", "<Shift-MouseWheel>"):
            self.bind_all(ev, self._wheel, add="+")
        enable_touch_scroll(self, self._canvas, lambda: self._sb.winfo_ismapped())

    def _on_scroll(self, first, last):
        self._sb.set(first, last)
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._sb.pack_forget()
        elif not self._sb.winfo_ismapped():
            self._sb.pack(side="right", fill="y", padx=(4, 0))

    def _bind_wheel(self, _e=None):
        pass                                                         # ahora un único enlace global (ver __init__)

    def _unbind_wheel(self, _e=None):
        pass

    def _wheel(self, e):
        if not wheel_over(self, e):
            return
        if self._sb.winfo_ismapped():
            n = wheel_units(self, e)
            if n:
                self._canvas.yview_scroll(n, "units")

    def to_top(self):
        self._canvas.yview_moveto(0)


class Swatch(tk.Canvas):
    """Cuadro de color redondeado y clicable (selector de colores por modo)."""

    def __init__(self, parent, color, command=None, size=34):
        ensure(parent)
        pbg = parent.cget("bg") if "bg" in parent.keys() else CANVAS
        super().__init__(parent, width=size, height=size, bg=pbg, highlightthickness=0, bd=0, cursor="hand2")
        self._size, self._command = size, command
        self.set(color)
        self.bind("<Button-1>", lambda e: command() if command else None)

    def set(self, color):
        self.color = color
        self.delete("all")
        round_rect(self, 1, 1, self._size - 1, self._size - 1, 9, fill=color, outline=CTRL_BORDER)


class ThemeTile(tk.Canvas):
    """Vista previa clicable de un tema de color en la apariencia actual."""

    def __init__(self, parent, theme, appearance, name, selected, command, width=120, height=70):
        import themes
        ensure(parent)
        pbg = parent.cget("bg") if "bg" in parent.keys() else CANVAS
        super().__init__(parent, width=width, height=height, bg=pbg, highlightthickness=0, bd=0, cursor="hand2")
        pal = themes.derive(theme, appearance) if theme else (DARK if appearance == "dark" else LIGHT)
        w, h = width, height
        round_rect(self, 1, 1, w - 1, h - 1, 12, fill=pal["CANVAS"],
                   outline=PRIMARY if selected else pal["LINE"], width=3 if selected else 1)
        round_rect(self, 9, 9, w - 9, 40, 8, fill=pal["SURFACE"], outline=pal["LINE"])
        round_rect(self, 15, 16, 47, 26, 5, fill=pal["PRIMARY"], outline="")
        for i, key in enumerate(("MODE_C", "MODE_P")):
            self.create_oval(55 + i * 14, 16, 65 + i * 14, 26, fill=pal[key], outline="")
        self.create_rectangle(15, 31, w - 40, 34, fill=pal["MUTED"], outline="")
        self.create_text(12, h - 15, text=name, anchor="w", fill=pal["INK"], font=F("small_bold"),
                         width=w - 24)
        self.bind("<Button-1>", lambda e: command())


_icons = {}


def set_window_icon(win):
    """Ícono de la app en la barra de título/tareas (PNG nativo de Tk; .ico además en Windows)."""
    import os
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    try:
        imgs = []
        for name in ("icon-256.png", "icon-64.png"):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                if name not in _icons:
                    _icons[name] = tk.PhotoImage(file=path)
                imgs.append(_icons[name])
        if imgs:
            win.iconphoto(True, *imgs)        # True: también las ventanas que se creen después
        ico = os.path.join(folder, "icon.ico")
        if os.name == "nt" and os.path.exists(ico):
            win.iconbitmap(ico)
    except Exception:
        pass


def separator(parent):
    ensure(parent)
    return ttk.Separator(parent, orient="horizontal", style="App.TSeparator")


# --- Ventanas y diálogos --------------------------------------------------------
def make_window(parent, title, size, heading, minsize=None, eyebrow="FOCUS RELAY DESKTOP", hero_h=84, modal=False):
    """Toplevel con encabezado en degradado y zona de contenido sobre fondo azulado."""
    ensure(parent)
    top = tk.Toplevel(parent)
    top.title(title)
    set_window_icon(top)
    top.configure(bg=CANVAS)
    try:
        w, h = (int(v) for v in size.split("+")[0].split("x"))
        size = f"{min(scaled(w), parent.winfo_screenwidth() - 40)}x{min(scaled(h), parent.winfo_screenheight() - 80)}"
    except (ValueError, AttributeError):
        pass
    top.geometry(size)
    if minsize:
        top.minsize(min(scaled(minsize[0]), parent.winfo_screenwidth() - 40),
                    min(scaled(minsize[1]), parent.winfo_screenheight() - 80))
    if modal:
        top.transient(parent)
    hero = Hero(top, heading, eyebrow=eyebrow, height=hero_h)
    hero.pack(fill="x")
    content = tk.Frame(top, bg=CANVAS)
    content.pack(fill="both", expand=True, padx=18, pady=(16, 16))
    return top, hero, content


def _center(top, parent):
    top.update_idletasks()
    try:
        x = parent.winfo_rootx() + (parent.winfo_width() - top.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - top.winfo_height()) // 3
        top.geometry(f"+{max(0, x)}+{max(0, y)}")
    except tk.TclError:
        pass


def _modal(parent, title, builder, width=420):
    """Diálogo modal pequeño con estilo propio. `builder(frame, close)` arma el contenido."""
    ensure(parent)
    top = tk.Toplevel(parent)
    top.title(title)
    top.configure(bg=CANVAS)
    top.transient(parent)
    top.resizable(False, False)
    card = Card(top, expand=False)
    card.pack(fill="both", expand=True, padx=14, pady=14)
    card.configure(width=width)
    result = {}

    def close(value=None):
        result["v"] = value
        top.destroy()

    builder(card.body, close)
    top.protocol("WM_DELETE_WINDOW", lambda: close(None))
    top.update_idletasks()
    _center(top, parent)
    try:
        top.grab_set()
    except tk.TclError:
        pass
    top.wait_window()
    return result.get("v")


class Tooltip:
    """Globito con texto al pasar el mouse por un widget. `text` puede ser un str o una función que lo devuelve."""

    def __init__(self, widget, text, delay=180):
        self.widget, self.text, self.delay = widget, text, delay
        self._tip, self._job = None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _schedule(self, _e=None):
        self._hide()
        self._job = self.widget.after(self.delay, self._show)

    def _show(self):
        self._job = None
        text = self.text() if callable(self.text) else self.text
        if not text or self._tip is not None:
            return
        try:
            x, y = self.widget.winfo_pointerx() + 14, self.widget.winfo_pointery() + 18
            tip = tk.Toplevel(self.widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x}+{y}")
            try:
                tip.attributes("-topmost", True)
            except tk.TclError:
                pass
            tk.Label(tip, text=text, bg=INK, fg=SURFACE, font=F("small_bold"), padx=10, pady=5).pack()
            self._tip = tip
        except tk.TclError:
            self._tip = None

    def _hide(self, _e=None):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except (tk.TclError, ValueError):
                pass
            self._job = None
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None


def ask_text(parent, title, prompt, initial=""):
    def build(body, close):
        label(body, prompt, bg=SURFACE, wraplength=360).pack(fill="x", pady=(0, 8))
        var = tk.StringVar(value=initial)
        e = entry(body, var)
        e.pack(fill="x")
        e.focus_set()
        e.bind("<Return>", lambda _e: close(var.get().strip()))
        e.bind("<Escape>", lambda _e: close(None))
        row = tk.Frame(body, bg=SURFACE)
        row.pack(fill="x", pady=(14, 0))
        Button(row, "Agregar", lambda: close(var.get().strip())).pack(side="right")
        Button(row, "Cancelar", lambda: close(None), style="ghost").pack(side="right", padx=(0, 8))
    return _modal(parent, title, build)


def ask_code(parent, title, text, code, ok, cancel, wrong, case_sensitive=False):
    """Pide escribir `code` tal como aparece (no se puede pegar). True si coincide; Enter acepta y Esc cancela."""
    import guard

    def build(body, close):
        label(body, title, kind="title", bg=SURFACE).pack(fill="x")
        label(body, text, bg=SURFACE, wraplength=360).pack(fill="x", pady=(6, 12))
        shown = tk.Label(body, text=code, bg=GHOST_BG, fg=ACCENT, font=(F("h1")[0], 20, "bold"), pady=10)
        shown.pack(fill="x")
        var = tk.StringVar()
        e = entry(body, var)
        e.pack(fill="x", pady=(12, 0))
        e.focus_set()
        for seq in ("<<Paste>>", "<Control-v>", "<Control-V>", "<Shift-Insert>", "<Button-2>"):
            e.bind(seq, lambda _e: "break")                   # hay que escribirlo, no pegarlo
        err = label(body, "", kind="muted", bg=SURFACE, wraplength=360)
        err.pack(fill="x", pady=(6, 0))

        def accept(_e=None):
            if guard.code_matches(code, var.get(), case_sensitive):
                close(True)
            else:
                err.configure(text=wrong, fg=DANGER)
                var.set("")
        e.bind("<Return>", accept)
        e.bind("<KP_Enter>", accept)
        e.bind("<Escape>", lambda _e: close(False))
        row = tk.Frame(body, bg=SURFACE)
        row.pack(fill="x", pady=(12, 0))
        Button(row, ok, accept, style="danger").pack(side="right")
        Button(row, cancel, lambda: close(False), style="ghost").pack(side="right", padx=(0, 8))
    return bool(_modal(parent, title, build))


def confirm(parent, title, message, yes="Continuar", danger=False):
    def build(body, close):
        label(body, title, kind="title", bg=SURFACE).pack(fill="x")
        label(body, message, bg=SURFACE, wraplength=360).pack(fill="x", pady=(6, 0))
        row = tk.Frame(body, bg=SURFACE)
        row.pack(fill="x", pady=(16, 0))
        Button(row, yes, lambda: close(True), style="danger" if danger else "primary").pack(side="right")
        Button(row, "Cancelar", lambda: close(False), style="ghost").pack(side="right", padx=(0, 8))
    return bool(_modal(parent, title, build))


def confirm_stop(parent, title, message, quote, keep, stop, dont_ask):
    """Confirmación al terminar antes de tiempo. Devuelve (terminar: bool, no_volver_a_preguntar: bool).
    Cerrar la ventana, Esc o Enter equivalen a seguir enfocado (la opción segura)."""
    state = {"ask": tk.BooleanVar(value=False)}

    def build(body, close):
        label(body, title, kind="title", bg=SURFACE).pack(fill="x")
        label(body, message, bg=SURFACE, wraplength=380).pack(fill="x", pady=(6, 12))
        box = tk.Frame(body, bg=GHOST_BG)
        box.pack(fill="x")
        tk.Frame(box, bg=PRIMARY, width=4).pack(side="left", fill="y")
        tk.Label(box, text=quote, bg=GHOST_BG, fg=ACCENT, font=F("bold"), wraplength=340, justify="left",
                 anchor="w").pack(side="left", fill="x", expand=True, padx=12, pady=12)
        if dont_ask:                                     # en modo estricto no se ofrece «no volver a preguntar»
            checkbutton(body, dont_ask, state["ask"], bg=SURFACE).pack(fill="x", pady=(12, 0))
        row = tk.Frame(body, bg=SURFACE)
        row.pack(fill="x", pady=(14, 0))
        keep_btn = Button(row, keep, lambda: close(False), style="primary")
        keep_btn.pack(side="right")
        Button(row, stop, lambda: close(True), style="danger").pack(side="right", padx=(0, 8))
        top = body.winfo_toplevel()
        top.bind("<Escape>", lambda _e: close(False))
        top.bind("<Return>", lambda _e: close(False))
        keep_btn.focus_set()
    result = _modal(parent, title, build, width=440)
    return bool(result), bool(state["ask"].get())


def inform(parent, title, message, kind="info"):
    def build(body, close):
        label(body, title, kind="title", bg=SURFACE).pack(fill="x")
        label(body, message, bg=SURFACE, wraplength=360).pack(fill="x", pady=(6, 0))
        row = tk.Frame(body, bg=SURFACE)
        row.pack(fill="x", pady=(16, 0))
        Button(row, "Entendido", lambda: close(True)).pack(side="right")
    _modal(parent, title, build)
