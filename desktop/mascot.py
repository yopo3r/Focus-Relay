"""Mascota opcional de Focus Relay: «Brote», una criatura redonda con un retoño que crece con tu racha.

* Lógica pura (estado de ánimo, mensajes, nivel de crecimiento): se prueba sin interfaz.
* Dibujo en un Canvas de tkinter con formas simples (sin imágenes ni dependencias): `draw(canvas, ...)`.
* `MascotWindow` es una ventanita flotante, sin bordes, siempre al frente (opcional), que se arrastra a cualquier
  lugar de la pantalla y cambia de tamaño (rueda del mouse, menú con clic derecho o Ajustes).
  Clic: la anima y recibe un ánimo.
"""
import math
import os
import random
import sys
import time
from datetime import datetime

import ui
from i18n import t

MOODS = ("idle", "focus", "break", "party", "sleepy", "wary", "invite", "hello")
PARTY_SECONDS = 4.5
INVITE_CHANCE = 0.5
RESUME_GAP = 20            # segundos sin latido del reloj interno => el equipo estuvo en suspensión
MESSAGE_SECONDS = 120          # cada cuánto aparece un mensaje por sí sola
BUBBLE_SECONDS = 7


def anim_delay(mood, poke_left=0, eco=False, draw_ms=0.0):
    """Milisegundos hasta el próximo cuadro. Rápido solo cuando hay algo vistoso (fiesta, toque); en reposo basta con
    pocos cuadros por segundo, y si dibujar tarda mucho (equipo lento) se espacia más para no acaparar el procesador."""
    base = 90 if (mood == "party" or poke_left > 0) else 200
    if eco:
        base = max(base, 700)
    return int(min(1500, max(base, draw_ms * 8)))


def bubble_seconds(text):
    """Tiempo que el globo queda visible: más para los mensajes largos (lectura ~15 caracteres por segundo)."""
    return max(BUBBLE_SECONDS, 5 + len(text or "") / 15.0)
SIZE = 96                      # el dibujo está pensado en una cuadrícula de 96; `Scaled` lo adapta
MIN_PX, MAX_PX, DEFAULT_PX = 56, 240, 110
KEY_COLOR = "#010203"           # color transparente en Windows

# Colores del cuerpo: (relleno, borde, brillo, mejillas). El retoño siempre es verde.
PALETTES = {
    "peach": ("#ffd9b0", "#e3b27f", "#fff0dc", "#ff9aa2"),
    "mint": ("#bfeedd", "#7fc9ac", "#eafff6", "#ff9aa2"),
    "sky": ("#bfdcff", "#7fa9e0", "#eaf4ff", "#ff9aa2"),
    "lavender": ("#d9c8ff", "#a68de0", "#f1eaff", "#ff9aa2"),
    "rose": ("#ffc4d6", "#e08aa8", "#ffeaf1", "#ff7f9f"),
    "lemon": ("#fff0a8", "#e0c860", "#fffbe0", "#ff9aa2"),
    "cloud": ("#f1f1f5", "#b9b9c9", "#ffffff", "#ffa6b0"),
}
DEFAULT_PALETTE = "peach"


def palette_for(name):
    return PALETTES.get(name) or PALETTES[DEFAULT_PALETTE]
INK_DARK = "#3b2f2f"
LEAF, LEAF_DARK = "#5cbf6e", "#3e9e54"
PETAL, PETAL_CORE, STAR = "#ff8fb1", "#ffd54a", "#ffd54a"


# --------------------------------------------------------------------------- lógica pura
def growth_level(streak):
    """0 brote, 1 dos hojas, 2 tres hojas, 3 flor: crece con los días seguidos de enfoque (2, 4 y 7)."""
    return 0 if streak < GROWTH_DAYS[0] else 1 if streak < GROWTH_DAYS[1] else 2 if streak < GROWTH_DAYS[2] else 3


GROWTH_DAYS = (2, 4, 7)


_WARY = {"until": 0.0}


def set_wary(on, seconds=300):
    """Brote te mira con sospecha mientras intentas terminar una sesión antes de tiempo (caduca sola por seguridad)."""
    _WARY["until"] = time.time() + seconds if on else 0.0


def is_wary(now=None):
    return (time.time() if now is None else now) < _WARY["until"]


def mood_for(estado, party_until=0.0, now=None, hour=None, wary=False):
    """Estado de ánimo según la sesión (`estado` del temporizador), una celebración reciente, la hora y si desconfía."""
    now = time.time() if now is None else now
    if now < party_until:
        return "party"
    if wary:
        return "wary"
    if estado and estado.get("ejecutando"):
        return "break" if estado.get("modo") == "P" and estado.get("fase") == "D" else "focus"
    hour = datetime.now().hour if hour is None else hour
    return "sleepy" if 0 <= hour < 5 else "idle"


def split_pool(text):
    """Los mensajes de cada estado viajan en una sola cadena separada por «|» (así encajan en el sistema de idiomas)."""
    return [p.strip() for p in str(text or "").split("|") if p.strip()]


def message_pool(mood, texts, custom=(), streak=0):
    """Mensajes posibles para `mood`. `texts` es {estado: cadena}; las frases propias del usuario se suman en
    reposo y en enfoque; con racha de 2 o más días se añade el recuento."""
    pool = split_pool(texts.get(mood, ""))
    if mood in ("idle", "focus"):
        pool += [c for c in custom if c]
    if mood == "idle" and streak >= 2 and texts.get("streak"):
        pool.append(texts["streak"].format(n=streak))
    return pool


def greeting_pool(texts, name="", hour=None, rng=random):
    """Saludo de bienvenida: por franja del día (mañana / tarde / noche) y, si hay nombre, a veces con él."""
    hour = time.localtime().tm_hour if hour is None else hour
    slot = "hello_m" if 5 <= hour < 12 else "hello_t" if 12 <= hour < 20 else "hello_n"
    name = (name or "").strip()
    if name and rng.random() < 0.6:
        pool = [s.format(name=name) for s in split_pool(texts.get("hello_name", "")) if "{name}" in s]
        if pool:
            return pool
    return split_pool(texts.get(slot, ""))


def pick(pool, last="", rng=random):
    """Elige un mensaje distinto del anterior cuando hay más de uno."""
    if not pool:
        return ""
    options = [m for m in pool if m != last] or pool
    return rng.choice(options)


# --------------------------------------------------------------------------- dibujo
def _star(c, x, y, r, color):
    c.create_polygon(x, y - r, x + r * 0.35, y - r * 0.35, x + r, y, x + r * 0.35, y + r * 0.35,
                     x, y + r, x - r * 0.35, y + r * 0.35, x - r, y, x - r * 0.35, y - r * 0.35,
                     fill=color, outline="")


def draw(c, mood="idle", frame=0, level=0, blink=False, poke=0, shadow=None, palette=DEFAULT_PALETTE):
    """Dibuja a Brote en el canvas `c` (de SIZE x SIZE). `frame` anima el vaivén; `poke` > 0 lo hace saltar."""
    BODY, BODY_EDGE, SHINE, CHEEK = palette_for(palette)
    cx = SIZE / 2
    bob = 2 * math.sin(frame / 6.0)
    if mood == "party":
        bob = -abs(11 * math.sin(frame / 2.2))
    elif poke > 0:
        bob = -abs(7 * math.sin(frame / 1.6)) * min(1.0, poke / 4.0)
    elif mood == "sleepy":
        bob = 1.2 * math.sin(frame / 10.0)
    dy = bob
    sway = 2 * math.sin(frame / 9.0)

    # sombra y pies
    c.create_oval(cx - 26, 88, cx + 26, 94, fill=shadow or ui.mix(ui.CANVAS, "#000000", 0.12), outline="")
    c.create_oval(cx - 20, 82 + dy / 2, cx - 4, 91, fill=BODY_EDGE, outline="")
    c.create_oval(cx + 4, 82 + dy / 2, cx + 20, 91, fill=BODY_EDGE, outline="")

    # retoño en la cabeza
    top = 36 + dy
    c.create_line(cx, top + 2, cx + sway / 2, top - 11, fill=LEAF_DARK, width=3, capstyle="round")
    tip_x, tip_y = cx + sway / 2, top - 11
    if level >= 3:                                              # flor
        for k in range(5):
            a = k * 2 * math.pi / 5 + frame / 40.0
            c.create_oval(tip_x + 6 * math.cos(a) - 4, tip_y - 3 + 6 * math.sin(a) - 4,
                          tip_x + 6 * math.cos(a) + 4, tip_y - 3 + 6 * math.sin(a) + 4, fill=PETAL, outline="")
        c.create_oval(tip_x - 4, tip_y - 7, tip_x + 4, tip_y + 1, fill=PETAL_CORE, outline="")
    else:
        c.create_oval(tip_x - 2, tip_y - 9, tip_x + 12, tip_y - 1, fill=LEAF, outline=LEAF_DARK)
        if level >= 1:
            c.create_oval(tip_x - 14, tip_y - 8, tip_x, tip_y, fill=LEAF, outline=LEAF_DARK)
        if level >= 2:
            c.create_oval(tip_x - 6, tip_y - 17, tip_x + 6, tip_y - 6, fill=LEAF, outline=LEAF_DARK)

    # brazos
    if (mood == "party" or poke > 0) and mood != "focus":      # leyendo, las manos ya sostienen el libro (si no, 4 brazos)
        c.create_oval(cx - 38, 42 + dy, cx - 26, 56 + dy, fill=BODY, outline=BODY_EDGE, width=2)
        c.create_oval(cx + 26, 42 + dy, cx + 38, 56 + dy, fill=BODY, outline=BODY_EDGE, width=2)
    elif mood in ("invite", "hello"):                            # una mano saluda, la otra queda abajo
        wave = 3 * math.sin(frame / 1.6)
        c.create_oval(cx - 36, 56 + dy, cx - 26, 72 + dy, fill=BODY, outline=BODY_EDGE, width=2)
        c.create_oval(cx + 26, 40 + dy + wave, cx + 37, 56 + dy + wave, fill=BODY, outline=BODY_EDGE, width=2)
    elif mood != "focus":                                        # leyendo, los brazos son las manos que sostienen el libro
        c.create_oval(cx - 36, 56 + dy, cx - 26, 72 + dy, fill=BODY, outline=BODY_EDGE, width=2)
        c.create_oval(cx + 26, 56 + dy, cx + 36, 72 + dy, fill=BODY, outline=BODY_EDGE, width=2)

    # cuerpo
    c.create_oval(cx - 31, top, cx + 31, 87 + dy / 2, fill=BODY, outline=BODY_EDGE, width=2)
    c.create_oval(cx - 22, top + 6, cx - 10, top + 14, fill=SHINE, outline="")      # brillo

    # cara
    ey = 58 + dy
    happy = mood in ("party", "break", "hello") or poke > 0
    if mood == "wary":                                           # mirada de reojo, párpados a media altura
        look = 3.5 if (frame // 25) % 2 else -3.5
        for sx in (-12, 12):
            c.create_oval(cx + sx - 5, ey - 4, cx + sx + 5, ey + 5, fill="#ffffff", outline=INK_DARK, width=1)
            c.create_oval(cx + sx + look - 2, ey - 2, cx + sx + look + 2.5, ey + 3, fill=INK_DARK, outline="")
            c.create_rectangle(cx + sx - 6, ey - 6, cx + sx + 6, ey - 1, fill=BODY, outline="")
            c.create_line(cx + sx - 6, ey - 1, cx + sx + 6, ey - 1, fill=INK_DARK, width=2)
    elif mood == "invite" and not blink:                         # ojos grandes y brillantes, cejas arriba
        for sx in (-12, 12):
            c.create_oval(cx + sx - 5.5, ey - 6.5, cx + sx + 5.5, ey + 5.5, fill=INK_DARK, outline="")
            c.create_oval(cx + sx - 3, ey - 5, cx + sx + 0.5, ey - 1.5, fill="#ffffff", outline="")
            c.create_oval(cx + sx + 1.5, ey + 0.5, cx + sx + 3.5, ey + 2.5, fill="#ffffff", outline="")
            c.create_arc(cx + sx - 6, ey - 15, cx + sx + 6, ey - 7, start=30, extent=120, style="arc", outline=INK_DARK, width=2)
    elif mood == "sleepy":
        for sx in (-12, 12):
            c.create_arc(cx + sx - 5, ey - 3, cx + sx + 5, ey + 5, start=200, extent=140, style="arc",
                         outline=INK_DARK, width=2)
    elif happy:
        for sx in (-12, 12):
            c.create_arc(cx + sx - 5, ey - 4, cx + sx + 5, ey + 6, start=20, extent=140, style="arc",
                         outline=INK_DARK, width=2)
    elif blink:
        for sx in (-12, 12):
            c.create_line(cx + sx - 4, ey, cx + sx + 4, ey, fill=INK_DARK, width=2, capstyle="round")
    else:
        for sx in (-12, 12):
            c.create_oval(cx + sx - 4, ey - 5, cx + sx + 4, ey + 5, fill=INK_DARK, outline="")
            c.create_oval(cx + sx - 2, ey - 3, cx + sx + 0.5, ey - 0.5, fill="#ffffff", outline="")
    if mood == "focus" and not blink:                            # cejas decididas
        c.create_line(cx - 17, ey - 10, cx - 8, ey - 10, fill=INK_DARK, width=2, capstyle="round")
        c.create_line(cx + 17, ey - 10, cx + 8, ey - 10, fill=INK_DARK, width=2, capstyle="round")
    c.create_oval(cx - 25, ey + 3, cx - 17, ey + 9, fill=CHEEK, outline="")
    c.create_oval(cx + 17, ey + 3, cx + 25, ey + 9, fill=CHEEK, outline="")
    if mood == "invite":                                         # sonrisa abierta
        c.create_arc(cx - 6, ey + 1, cx + 6, ey + 13, start=180, extent=180, style="chord", fill="#b5474f", outline=INK_DARK, width=2)
    elif mood == "party":
        c.create_oval(cx - 5, ey + 5, cx + 5, ey + 14, fill="#b5474f", outline=INK_DARK, width=1)
    elif mood == "wary":
        c.create_line(cx - 5, ey + 9, cx + 5, ey + 8, fill=INK_DARK, width=2, capstyle="round")
    elif mood == "sleepy":
        c.create_oval(cx - 2, ey + 7, cx + 2, ey + 11, fill=INK_DARK, outline="")
    else:
        c.create_arc(cx - 5, ey + 3, cx + 5, ey + 11, start=210, extent=120, style="arc", outline=INK_DARK, width=2)

    # accesorios según el ánimo
    if mood == "focus":                                          # libro sostenido frente a la cara: se ve su tapa trasera
        d = dy / 2
        cover = ui.PRIMARY
        edge = ui.mix(ui.PRIMARY, "#000000", 0.35)
        spine = ui.mix(ui.PRIMARY, "#000000", 0.22)
        c.create_rectangle(cx - 19, 66 + d, cx + 21, 69 + d, fill="#fffdf5", outline="#b9b3a0")      # canto de las páginas
        c.create_rectangle(cx - 22, 68 + d, cx + 22, 91 + d, fill=cover, outline=edge, width=2)       # tapa
        c.create_rectangle(cx - 22, 68 + d, cx - 16, 91 + d, fill=spine, outline=edge, width=1)       # lomo
        c.create_rectangle(cx - 9, 73 + d, cx + 15, 82 + d, fill="#fffdf5", outline="#b9b3a0")        # etiqueta del título
        c.create_line(cx - 6, 76 + d, cx + 12, 76 + d, fill="#a7a291", width=1)
        c.create_line(cx - 6, 79 + d, cx + 8, 79 + d, fill="#a7a291", width=1)
        c.create_oval(cx - 27, 77 + d, cx - 17, 88 + d, fill=BODY, outline=BODY_EDGE, width=2)       # manitas
        c.create_oval(cx + 17, 77 + d, cx + 27, 88 + d, fill=BODY, outline=BODY_EDGE, width=2)
    elif mood == "break":                                        # notas de música / calma
        c.create_text(cx + 38, 30 + 3 * math.sin(frame / 5.0), text="♪", fill=ui.MUTED, font=("TkDefaultFont", 13, "bold"))
    elif mood == "sleepy":
        c.create_text(cx + 34, 26 - (frame % 20) / 2.0, text="z", fill=ui.MUTED, font=("TkDefaultFont", 12, "bold"))
        c.create_text(cx + 42, 16 - (frame % 20) / 2.5, text="Z", fill=ui.MUTED, font=("TkDefaultFont", 9, "bold"))
    elif mood == "wary":                                         # gotita de sudor
        c.create_oval(cx + 28, 34 + dy + (frame % 12) / 3.0, cx + 35, 44 + dy + (frame % 12) / 3.0, fill="#9ed8ff",
                      outline="#5aa9de")
    elif mood == "invite":                                       # destellos de entusiasmo
        _star(c, cx - 36, 22 + 2 * math.sin(frame / 2.0), 4, STAR)
        _star(c, cx + 40, 26 + 2 * math.sin(frame / 2.0 + 1), 3, STAR)
    elif mood == "party":
        for k, (sx, sy) in enumerate(((-38, 20), (36, 14), (-30, 62), (40, 54))):
            _star(c, cx + sx, sy + 3 * math.sin(frame / 2.0 + k), 4 + (frame + k) % 3, STAR)




def texts():
    """Mensajes por estado en el idioma actual (cadenas separadas por «|»)."""
    return {"idle": t("mascotaIdle"), "focus": t("mascotaFoco"), "break": t("mascotaDescanso"),
            "party": t("mascotaFiesta"), "wary": t("mascotaSospecha"), "sleepy": t("mascotaSueno"), "poke": t("mascotaToque"),
            "streak": t("mascotaRacha"), "invite": t("mascotaInvita"),
            "hello_m": t("mascotaSaludoM"), "hello_t": t("mascotaSaludoT"), "hello_n": t("mascotaSaludoN"),
            "hello_name": t("mascotaSaludoNombre")}


MIN_FONT, MAX_FONT, DEFAULT_FONT = 8, 22, 10


def clamp_font(pt):
    try:
        return max(MIN_FONT, min(MAX_FONT, int(pt)))
    except (TypeError, ValueError):
        return DEFAULT_FONT


def clamp_size(px):
    try:
        return max(MIN_PX, min(MAX_PX, int(px)))
    except (TypeError, ValueError):
        return DEFAULT_PX


def clamp_pos(x, y, w, h, screen_w, screen_h):
    """Mantiene la ventana dentro de la pantalla."""
    return max(0, min(int(x), max(0, screen_w - w))), max(0, min(int(y), max(0, screen_h - h)))


class Scaled:
    """Envuelve un canvas para dibujar en la cuadrícula de 96 a cualquier tamaño (coordenadas, grosores y fuentes)."""

    def __init__(self, canvas, px, tag=None):
        self.c, self.k, self.tag = canvas, px / float(SIZE), tag

    def delete(self, *a):
        self.c.delete(*a)

    def __getattr__(self, name):
        if not name.startswith("create_"):
            raise AttributeError(name)
        make, k, tag = getattr(self.c, name), self.k, self.tag

        def create(*args, **kw):
            args = [a * k if isinstance(a, (int, float)) else a for a in args]
            if "width" in kw:
                kw["width"] = max(1, round(kw["width"] * k))
            if "font" in kw and isinstance(kw["font"], tuple) and len(kw["font"]) > 1:
                kw["font"] = (kw["font"][0], max(6, round(kw["font"][1] * k))) + tuple(kw["font"][2:])
            if tag:
                kw["tags"] = tag
            return make(*args, **kw)
        return create


# --------------------------------------------------------------------------- ventana flotante
class MascotWindow:
    """Ventanita flotante con la mascota: sin bordes, arrastrable, redimensionable y (opcional) siempre al frente.

    Vive en la aplicación, no en el Panel: se ve aunque el Panel esté cerrado. Lee los ajustes cada par de segundos
    (`mascot`, `mascot_size`, `mascot_x/y`, `mascot_on_top`), así Ajustes y el menú de la bandeja solo escriben la
    configuración."""

    def __init__(self, root, get_state, get_cfg, save_cfg, get_texts, get_log, open_panel):
        import tkinter as tk
        self.tk, self.root = tk, root
        self.get_state, self.get_cfg, self.save_cfg = get_state, get_cfg, save_cfg
        self.get_texts, self.get_log, self.open_panel = get_texts, get_log, open_panel
        self.top = None
        self.cfg = {}
        self.streak = 0
        self.mood, self.estado, self.party_until = "idle", None, 0.0
        self.celebrate_seen = get_state()[1]
        self.message, self.message_at, self.bubble_until = "", 0.0, 0.0
        self.frame_no, self.poke_left, self.blink_until, self.next_blink = 0, 0, 0, 40
        self.mx = self.my = None            # esquina superior izquierda de la mascota (no de la ventana)
        self.size = DEFAULT_PX
        self.transparent = False
        self._drag = None
        self._cfg_pos = (None, None)
        self._last_lift = 0.0
        self._retry_at = 0.0
        self._shown = False
        self._topmost = None
        self._draw_ms = 0.0
        self.invite_until = 0.0
        self.hello_until = 0.0
        self._last_tick = time.time()
        self._bubble_t0 = 0.0
        self._greeted = False
        self._font_pt = None
        self.bwin = None                    # ventana aparte del globo: así la mascota nunca cambia de tamaño
        self._bubble_on = False
        self._streak_at = 0.0
        self._tick()

    # -- ciclo de vida
    def _tick(self):
        try:
            self.cfg = self.get_cfg()
            now = time.time()
            if self.top is not None and now - self._last_tick > RESUME_GAP:
                self._destroy()                                  # el equipo estuvo suspendido: se recrean las ventanas
            self._last_tick = now
            if self.top is not None and not self._alive():      # otra parte de la app la cerró (p. ej. al cambiar de tema)
                self._destroy()
            if self.cfg.get("mascot", True):
                if self.top is None and time.time() >= self._retry_at:
                    self._create()
                if self.top is not None:
                    self._sync()
            elif self.top is not None:
                self._destroy()
        except Exception as exc:
            print(f"[Focus Relay] mascota: {exc}")
        self.root.after(1000, self._tick)

    def _alive(self):
        try:
            return bool(self.top.winfo_exists()) and bool(self.bwin.winfo_exists())
        except self.tk.TclError:
            return False

    def _create(self):
        tk = self.tk
        top = tk.Toplevel(self.root)
        self.top = top
        try:
            top.withdraw()                                    # se muestra ya colocada, sin parpadear en la esquina (0, 0)
            top.overrideredirect(True)
            top.title("Focus Relay")
            self.transparent = False
            bg = ui.CANVAS
            try:
                if sys.platform.startswith("win"):
                    top.attributes("-transparentcolor", KEY_COLOR)
                    bg, self.transparent = KEY_COLOR, True
                elif sys.platform == "darwin":
                    top.attributes("-transparent", True)
                    bg, self.transparent = "systemTransparent", True
            except tk.TclError:
                bg, self.transparent = ui.CANVAS, False
            top.configure(bg=bg)
            self.frame = tk.Frame(top, bg=bg)
            self.frame.pack()
            self.bwin = tk.Toplevel(self.root)
            self.bwin.withdraw()
            self.bwin.overrideredirect(True)
            self.bubble = tk.Label(self.bwin, text="", bg=ui.SURFACE, fg=ui.INK, font=ui.F("small"), justify="left",
                                   wraplength=230, padx=10, pady=6, bd=1, relief="solid")
            self.bubble.pack()
            self.canvas = tk.Canvas(self.frame, width=DEFAULT_PX, height=DEFAULT_PX, highlightthickness=0, bd=0,
                                    bg=bg, cursor="fleur")
            self.canvas.pack(side="bottom")
            self.bg = bg
            for w in (self.canvas, self.bubble):
                w.bind("<ButtonPress-1>", self._press)
                w.bind("<B1-Motion>", self._motion)
                w.bind("<ButtonRelease-1>", self._release)
                w.bind("<Double-Button-1>", self._double)
                w.bind("<Button-3>", self._menu)
                w.bind("<Button-2>", self._menu)
                w.bind("<MouseWheel>", self._wheel)
                w.bind("<Button-4>", lambda e: self._resize(+8))
                w.bind("<Button-5>", lambda e: self._resize(-8))
        except Exception as exc:                              # no dejar una ventana a medias (se vería como un cuadro vacío)
            print(f"[Focus Relay] mascota: no se pudo crear la ventana: {exc}")
            self._destroy()
            self._retry_at = time.time() + 30
            return
        self.size = 0
        self._geom = None
        self._bgeom = None
        self.mx = self.my = None
        self._shown = False
        self._topmost = None
        self._bubble_on = False
        if not self._greeted:                            # al abrir la app, Brote saluda (una sola vez por sesión de la app)
            self._greeted = True
            self._greet()
        else:
            self._say(self.mood)
        self._anim()

    def _destroy(self):
        for w in (self.bwin, self.top):
            if w is not None:
                try:
                    w.destroy()
                except self.tk.TclError:
                    pass
        self.top = self.bwin = None
        self._shown = False
        self._bubble_on = False

    def _sync(self):
        """Aplica ajustes (tamaño, posición, al frente) y el estado del temporizador."""
        cfg = self.cfg
        size = clamp_size(cfg.get("mascot_size", DEFAULT_PX))
        pos = (cfg.get("mascot_x"), cfg.get("mascot_y"))
        if size != self.size:                    # el tamaño va primero: _place() depende de él
            self.size = size
            self.canvas.configure(width=size, height=size)
            self._geom = None
        if self.mx is None or (self._drag is None and pos != self._cfg_pos):      # primera vez o posición cambiada en Ajustes
            sw, sh = self.top.winfo_screenwidth(), self.top.winfo_screenheight()
            x, y = pos if None not in pos else (sw - size - 40, sh - size - 110)
            self.mx, self.my = clamp_pos(x, y, size, size, sw, sh)
            self._cfg_pos = pos
            self._geom = None
        fpt = clamp_font(cfg.get("mascot_font", DEFAULT_FONT))
        if fpt != self._font_pt:                  # tamaño de la letra del globo
            self._font_pt = fpt
            self.bubble.configure(font=(ui.F("small")[0], fpt), wraplength=int(fpt * 24))
            self._bgeom = None
        self._place()
        on_top = bool(cfg.get("mascot_on_top", True))
        if on_top != self._topmost:
            self._topmost = on_top
            self.top.attributes("-topmost", on_top)
            self.bwin.attributes("-topmost", on_top)
        now = time.time()
        if not self._shown:
            self._shown = True
            self.top.deiconify()
        if self._shown and not self.top.winfo_viewable():          # el sistema la ocultó (escritorio, cambio de ventanas…)
            self.top.deiconify()
            self._geom = None
            self._place()
        self._ensure_bubble_visible()
        if on_top and sys.platform.startswith("win") and now - self._last_lift > 5:
            # Otras ventanas «al frente» (video a pantalla completa, administrador de tareas) pueden quitarle el puesto.
            self._last_lift = now
            self.top.attributes("-topmost", True)
            self.top.lift()
            if self._bubble_on:
                self.bwin.attributes("-topmost", True)
                self.bwin.lift()
        if on_top and not sys.platform.startswith(("win", "darwin")) and now - self._last_lift > 1:
            # En X11 una ventana sin bordes queda tapada en cuanto otra se levanta: se vuelve a subir cada segundo.
            self._last_lift = now
            self.top.lift()
            if self._bubble_on:
                self.bwin.lift()
        estado, celebrate = self.get_state()
        self.estado = estado
        if celebrate != self.celebrate_seen:
            self.celebrate_seen = celebrate
            self.party_until = now + PARTY_SECONDS
            self._say("party")
        mood = mood_for(estado, self.party_until, wary=is_wary(now))
        if mood != self.mood:
            self.mood = mood
            self._say(mood)
        elif now - self.message_at > MESSAGE_SECONDS:
            self._say(mood)
        if now - self._streak_at > 60:
            self._streak_at = now
            self._load_streak()

    def _load_streak(self):
        import threading

        def work():
            try:
                self.streak = int(self.get_log() or 0)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    # -- mensajes
    def _greet(self):
        pool = greeting_pool(self.get_texts(), (self.cfg or {}).get("user_name", ""))
        text = pick(pool)
        if not text:
            self._say(self.mood)
            return
        self.message = text
        self.hello_until = time.time() + bubble_seconds(text)
        self._show_bubble(text)

    def _say(self, mood):
        pool = message_pool(mood, self.get_texts(), (self.cfg or {}).get("phrases", []), self.streak)
        if mood == "idle" and random.random() < INVITE_CHANCE:       # a veces, en reposo, propone empezar una sesión
            invite = message_pool("invite", self.get_texts())
            if invite:
                choice = pick(invite, self.message)
                pool = [choice]
                self.invite_until = time.time() + bubble_seconds(choice)
        self.message = pick(pool, self.message) or self.message
        self._show_bubble(self.message)

    def _show_bubble(self, text):
        now = time.time()
        self.message_at = now
        if not text or not (self.cfg or {}).get("mascot_text", True):
            return
        self.bubble.configure(text=text)
        self.bubble_until = now + bubble_seconds(text)
        was_on = self._bubble_on
        if not was_on:
            self._bubble_t0 = time.time()
        self._bubble_on = True
        self._place()                                    # se coloca antes de mostrarla
        if not was_on and self.bwin is not None and self.mx is not None and self.size:
            self.bwin.withdraw()                         # al mostrarla se vuelve a mapear siempre: tras suspender, el
            self.bwin.deiconify()                        # sistema puede dar por «visible» una ventana que ya no se ve
        self._ensure_bubble_visible()

    def _dbg(self, msg, always=False):
        """Pistas para diagnosticar fallos del globo: salen por consola (siempre las autorreparaciones; el resto con
        FOCUS_RELAY_DEBUG=1)."""
        if always or os.environ.get("FOCUS_RELAY_DEBUG") == "1":
            print(f"[Focus Relay] mascota: {msg}")

    def _ensure_bubble_visible(self):
        """Si el globo debería verse pero no se ve (ventana oculta, movida o tapada por el sistema), lo repara."""
        if not self._bubble_on or self.bwin is None or self.mx is None or not self.size:
            return
        try:
            if not self.bwin.winfo_viewable():
                self._dbg("el globo estaba oculto por el sistema; se vuelve a mostrar",
                          always=time.time() - self._bubble_t0 > 1.5)
                self.bwin.withdraw()
                self.bwin.deiconify()
            elif self._bgeom and "+" in self._bgeom:
                ex, ey = (int(v) for v in self._bgeom.lstrip("+").split("+"))
                if abs(self.bwin.winfo_rootx() - ex) > 4 or abs(self.bwin.winfo_rooty() - ey) > 4:
                    self._dbg("el globo estaba fuera de su sitio; se recoloca", always=True)
                    self._bgeom = None
                    self._place()
            if (self.cfg or {}).get("mascot_on_top", True):
                self.bwin.attributes("-topmost", True)       # tras ocultar/mostrar, Windows puede perder el «al frente»
                self.bwin.lift()
        except (self.tk.TclError, ValueError):
            pass

    def _hide_bubble(self, reason="expiró"):
        if self._bubble_on:
            self._dbg(f"globo oculto ({reason})")
            self._bubble_on = False
            self.bwin.withdraw()

    # -- geometría
    def _place(self):
        """La ventana de la mascota tiene tamaño fijo; el globo es otra ventana pegada encima (o debajo si no cabe)."""
        if self.top is None or self.mx is None or not self.size:
            return
        sw, sh = self.top.winfo_screenwidth(), self.top.winfo_screenheight()
        size = self.size
        x, y = clamp_pos(self.mx, self.my, size, size, sw, sh)
        geom = f"{size}x{size}+{x}+{y}"
        if geom != self._geom:
            self._geom = geom
            self.top.geometry(geom)
        if self._bubble_on and self.bwin is not None:
            self.bwin.update_idletasks()
            bw, bh = self.bwin.winfo_reqwidth(), self.bwin.winfo_reqheight()
            right = x + size / 2 > sw / 2                # en la mitad derecha el globo se alinea al borde derecho
            bx = x + size - bw if right else x
            by = y - bh - 2
            if by < 0:                                   # sin espacio arriba: va debajo
                by = y + size + 2
            bx, by = clamp_pos(bx, by, bw, bh, sw, sh)
            geom = f"+{bx}+{by}"
            if geom != self._bgeom:
                self._bgeom = geom
                self.bwin.geometry(geom)

    # -- animación
    def _anim(self):
        if self.top is None:
            return
        started = time.perf_counter()
        mood_now = mood_for(self.estado, self.party_until, wary=is_wary())
        if mood_now in ("idle", "break") and time.time() < self.hello_until:        # saludo de bienvenida
            mood_now = "hello"
        elif mood_now == "idle" and time.time() < self.invite_until:         # cara de «¿empezamos?» mientras dura la invitación
            mood_now = "invite"
        delay = anim_delay(mood_now, self.poke_left, bool((self.cfg or {}).get("eco_mode")), self._draw_ms)
        try:
            self.frame_no += max(1, round(delay / 120.0))           # la animación conserva su ritmo aunque haya menos cuadros
            if self.frame_no >= self.next_blink:
                self.blink_until = self.frame_no + 2
                self.next_blink = self.frame_no + random.randint(28, 60)
            if self.poke_left > 0:
                self.poke_left = max(0, self.poke_left - max(1, round(delay / 120.0)))
            if time.time() > self.bubble_until:
                self._hide_bubble()
            elif not (self.cfg or {}).get("mascot_text", True):
                self._hide_bubble("texto desactivado")
            level = growth_level(self.streak)
            shadow = "#b9b9c4" if self.transparent else None
            c = self.canvas
            c.configure(bg=self.bg)
            # Doble búfer: se dibuja el cuadro nuevo y recién entonces se borra el anterior (así no parpadea).
            draw(Scaled(c, self.size or DEFAULT_PX, tag="new"), mood_now, self.frame_no,
                 level, blink=self.frame_no < self.blink_until, poke=self.poke_left, shadow=shadow,
                 palette=self.cfg.get("mascot_color", DEFAULT_PALETTE))
            c.delete("old")
            c.addtag_withtag("old", "new")
            c.dtag("new", "new")
            self._draw_ms = 0.7 * self._draw_ms + 0.3 * (time.perf_counter() - started) * 1000.0
        except self.tk.TclError:
            self._destroy()                                       # la ventana se cerró: se libera y _tick la recreará
            return
        except Exception as exc:                                  # un error de dibujo no debe congelar a la mascota
            print(f"[Focus Relay] mascota: {exc}")
        try:
            self.top.after(delay, self._anim)
        except self.tk.TclError:
            self._destroy()

    # -- interacción
    def _press(self, e):
        self._drag = {"x": e.x_root, "y": e.y_root, "mx": self.mx, "my": self.my, "moved": False}

    def _motion(self, e):
        d = self._drag
        if not d:
            return
        dx, dy = e.x_root - d["x"], e.y_root - d["y"]
        if not d["moved"] and abs(dx) + abs(dy) < 8:
            return
        d["moved"] = True
        sw, sh = self.top.winfo_screenwidth(), self.top.winfo_screenheight()
        self.mx, self.my = clamp_pos(d["mx"] + dx, d["my"] + dy, self.size, self.size, sw, sh)
        self._place()

    def _double(self, _e=None):
        """Doble clic / doble toque: abre el Panel."""
        self._drag = None
        try:
            self.open_panel()
        except Exception as exc:
            print(f"[Focus Relay] mascota: {exc}")

    def _release(self, e):
        d, self._drag = self._drag, None
        if not d:
            return
        if d["moved"]:
            self._cfg_pos = (int(self.mx), int(self.my))
            self.save_cfg(mascot_x=int(self.mx), mascot_y=int(self.my))
        else:
            self.poke_left = 14
            self._say("poke")

    def _wheel(self, e):
        self._resize(+8 if e.delta > 0 else -8)

    def _resize(self, delta):
        size = clamp_size(self.size + delta)
        if size != self.size:
            self.save_cfg(mascot_size=size)
            self.cfg["mascot_size"] = size

    def _menu(self, e):
        tk = self.tk
        menu = tk.Menu(self.top, tearoff=0)
        for key, px in (("mascotaTamPeq", 72), ("mascotaTamMed", 110), ("mascotaTamGra", 160), ("mascotaTamEnorme", 220)):
            label = ("● " if abs(self.size - px) < 12 else "   ") + t(key)
            menu.add_command(label=label, command=lambda px=px: self._set_size(px))
        menu.add_separator()
        on_top = bool(self.cfg.get("mascot_on_top", True))
        menu.add_command(label=("✓ " if on_top else "   ") + t("mascotaAlFrente"),
                         command=lambda: self.save_cfg(mascot_on_top=not on_top))
        menu.add_command(label=t("trayAbrir"), command=self.open_panel)
        menu.add_command(label=t("mascotaOcultar"), command=lambda: self.save_cfg(mascot=False))
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    def _set_size(self, px):
        self.save_cfg(mascot_size=px)
        self.cfg["mascot_size"] = px
