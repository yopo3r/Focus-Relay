"""Celebración al terminar una sesión: confeti que cae sobre la ventana con una tarjeta de felicitación.

Todo se dibuja en un Canvas que cubre la ventana (Tk no tiene transparencia portable); el fondo se
atenúa con un patrón punteado para que las piezas y la tarjeta destaquen. Se cierra solo o con un clic.
"""
import math
import random
import time
import tkinter as tk

import emoji_img
import ui


def _colors():
    return [ui.PRIMARY, ui.SUCCESS, ui.MODE_T if hasattr(ui, "MODE_T") else ui.PRIMARY_2, ui.PRIMARY_2,
            ui.DANGER, "#f5b800", "#ff7a59", "#35c6d0"]


class Confetti:
    DURATION_MS = 5000
    FRAME_MS = 33

    def __init__(self, top, title, subtitle, trophy=None):
        self.top = top
        self._photo = None
        self.alive = True
        self.cv = tk.Canvas(top, highlightthickness=0, bd=0, bg=ui.CANVAS, cursor="hand2")
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self.cv)
        top.update_idletasks()
        self.w, self.h = max(top.winfo_width(), 400), max(top.winfo_height(), 300)
        self.cv.create_rectangle(0, 0, self.w, self.h, fill=ui.mix(ui.CANVAS, ui.PRIMARY, 0.14), outline="")
        self._card(title, subtitle, trophy)
        cols = _colors()
        self.parts = []
        for _ in range(130):
            self.parts.append({
                "x": random.uniform(0, self.w), "y": random.uniform(-self.h * 0.45, -10),
                "vx": random.uniform(-2.0, 2.0), "vy": random.uniform(8.0, 15.0),
                "w": random.uniform(6, 12), "h": random.uniform(4, 8),
                "a": random.uniform(0, math.tau), "va": random.uniform(-0.3, 0.3),
                "sway": random.uniform(0, math.tau), "col": random.choice(cols), "id": None,
            })
        self.cv.bind("<Button-1>", lambda e: self.close())
        top.bind("<Escape>", lambda e: self.close(), add="+")
        self.elapsed = 0
        self._last = time.monotonic()
        self._step()

    def _card(self, title, subtitle, trophy=None):
        """Tarjeta de felicitación. Con `trophy` ({piece, count, caption, ach_caption}) muestra la pieza ganada
        y los logros desbloqueados con esta sesión."""
        cx, cy = self.w / 2, self.h / 2
        import tkinter.font as tkfont
        ft, fs = tkfont.Font(font=ui.F("h1")), tkfont.Font(font=ui.F("body"))
        piece = (trophy or {}).get("piece")
        lines = list((trophy or {}).get("ach_caption") or [])
        caption = ""
        if piece:
            n = trophy.get("count", 1)
            caption = ("+%d  " % n if n > 1 else "") + trophy.get("caption", "")
        widest = max([ft.measure(title), min(fs.measure(subtitle), 420)] + [min(fs.measure(x), 420) for x in lines + [caption]])
        wid = widest + 80
        hei = 120 + (112 if piece else 0) + 26 * len(lines) + (8 if lines and not piece else 0)
        top = cy - hei / 2
        ui.round_rect(self.cv, cx - wid / 2, top, cx + wid / 2, top + hei, 20, fill=ui.SURFACE, outline=ui.LINE)
        self.cv.create_text(cx, top + 42, text=title, font=ui.F("h1"), fill=ui.INK)
        self.cv.create_text(cx, top + 80, text=subtitle, font=ui.F("body"), fill=ui.MUTED, width=420)
        y = top + 112
        if piece:                                           # la pieza ganada, en su mosaico de color
            size = 64
            ui.round_rect(self.cv, cx - size / 2, y, cx + size / 2, y + size, 16, fill=piece["color"], outline=piece["color"])
            self._photo = emoji_img.photo(piece["icon"], 40)
            if self._photo is not None:
                self.cv.create_image(cx, y + size / 2, image=self._photo)
            else:
                self.cv.create_text(cx, y + size / 2, text=piece["icon"], font=(ui.F("h1")[0], 26))
            self.cv.create_text(cx, y + size + 18, text=caption, font=ui.F("bold"), fill=ui.ACCENT, width=420)
            y += size + 38
        for text in lines:
            self.cv.create_text(cx, y + 14, text="🏆 " + text, font=ui.F("bold"), fill=ui.ACCENT, width=420)
            y += 26

    def _step(self):
        if not self.alive:
            return
        try:
            if not self.cv.winfo_exists():
                return
        except tk.TclError:
            return
        now = time.monotonic()                              # movimiento según tiempo real (equipos lentos)
        dt = min(now - self._last, 0.2) * 1000.0
        self._last = now
        self.elapsed += dt
        k = dt / self.FRAME_MS
        left = 0
        for p in self.parts:
            p["y"] += p["vy"] * k
            p["sway"] += 0.07 * k
            p["x"] += (p["vx"] + math.sin(p["sway"]) * 0.9) * k
            p["a"] += p["va"] * k
            if p["y"] > self.h + 20:
                if p["id"] is not None:
                    self.cv.delete(p["id"])
                    p["id"] = None
                continue
            left += 1
            if p["y"] < -20:
                continue
            c, s = math.cos(p["a"]), math.sin(p["a"])
            hw, hh = p["w"] / 2, p["h"] / 2 * abs(math.cos(p["sway"]))        # "voltea" la pieza al caer
            pts = []
            for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
                pts += [p["x"] + dx * c - dy * s, p["y"] + dx * s + dy * c]
            if p["id"] is None:
                p["id"] = self.cv.create_polygon(pts, fill=p["col"], outline="")
            else:
                self.cv.coords(p["id"], *pts)
        if left == 0 or self.elapsed > self.DURATION_MS + 1500:
            self.close()
            return
        self.cv.after(self.FRAME_MS, self._step)

    def close(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.cv.destroy()
        except tk.TclError:
            pass


_current = {"c": None}


def celebrate(top, title, subtitle, trophy=None):
    """Lanza el confeti sobre `top` (si ya hay uno en curso, lo reemplaza)."""
    old = _current["c"]
    if old is not None:
        old.close()
    _current["c"] = Confetti(top, title, subtitle, trophy)
    return _current["c"]
