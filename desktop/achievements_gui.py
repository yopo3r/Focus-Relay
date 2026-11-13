"""Pestaña "Logros": resumen, cuatro secciones (rachas, tiempo de enfoque, tareas, largo de sesiones) y colección."""
import tkinter as tk

import insights
import share_gui
import tasks
import trophies
import ui
from i18n import t

GOAL_FMT = {"streak": "statDias", "hours": "logroValH", "marathon": "logroValMin"}
VALUE_FMT = {"streak": "statDias", "hours": "logroValH", "marathon": "logroValMin"}


def fmt_goal(fam, n):
    key = GOAL_FMT.get(fam)
    return t(key, n=n) if key else str(n)


def fmt_value(fam, v):
    if fam == "hours":
        v = round(v, 1) if v < 10 else int(v)
    elif isinstance(v, float):
        v = int(v)
    key = VALUE_FMT.get(fam)
    return t(key, n=v) if key else str(v)


class Timeline(tk.Canvas):
    """Línea de metas: puntos equiespaciados, la barra avanza según el valor actual."""

    def __init__(self, parent, fam, value, goals, on_share):
        super().__init__(parent, height=int(52 * max(1.0, ui.TEXT_SCALE * 0.95)), bg=ui.SURFACE,
                         highlightthickness=0, bd=0)
        self.fam, self.value, self.goals, self.on_share = fam, value, goals, on_share
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        self.delete("all")
        w, n = self.winfo_width(), len(self.goals)
        if w < 80 or not n:
            return
        x0, x1, y = 34, w - 34, 14
        xs = [x0 + (x1 - x0) * i / max(1, n - 1) for i in range(n)]
        v = self.value
        goals = [g for g, _ in self.goals]
        if v >= goals[-1]:
            px = x1
        elif v < goals[0]:
            px = 8 + (x0 - 8) * (v / goals[0])
        else:
            i = max(k for k, g in enumerate(goals) if g <= v)
            px = xs[i] + (xs[i + 1] - xs[i]) * ((v - goals[i]) / (goals[i + 1] - goals[i]))
        self.create_line(8, y, x1, y, fill=ui.LINE, width=3, capstyle="round")
        if px > 8:
            self.create_line(8, y, px, y, fill=ui.ACCENT, width=3, capstyle="round")
        for x, (g, done) in zip(xs, self.goals):
            tag = f"g{g}"
            if done:
                self.create_oval(x - 7, y - 7, x + 7, y + 7, fill=ui.ACCENT, outline=ui.ACCENT, tags=tag)
                self.create_line(x - 3, y, x - 1, y + 3, x + 4, y - 3, fill=ui.WHITE if ui.lum(ui.ACCENT) < 0.6 else ui.INK,
                                 width=2, tags=tag)
                self.tag_bind(tag, "<Button-1>", lambda e, g=g: self.on_share(g))
                self.tag_bind(tag, "<Enter>", lambda e: self.configure(cursor="hand2"))
                self.tag_bind(tag, "<Leave>", lambda e: self.configure(cursor="arrow"))
            else:
                self.create_oval(x - 6, y - 6, x + 6, y + 6, fill=ui.SURFACE, outline=ui.LINE, width=2)
            self.create_text(x, y + 22, text=fmt_goal(self.fam, g), font=ui.F("tiny"),
                             fill=ui.INK if done else ui.MUTED)


def _summary(dash, parent, tot):
    got, total, nxt = trophies.overall(tot)
    card = ui.Card(parent, pad=20)
    card.pack(fill="x", pady=(0, 14))
    row = tk.Frame(card.body, bg=ui.SURFACE)
    row.pack(fill="x")
    big = tk.Label(row, text=str(got), bg=ui.SURFACE, fg=ui.ACCENT, font=(ui.F("clock")[0], int(ui.F("clock")[1] * 0.9), "bold"))
    big.pack(side="left")
    box = tk.Frame(row, bg=ui.SURFACE)
    box.pack(side="left", padx=14)
    dash._lbl(box, t("statLogrosCuenta", a=got, b=total), "bold").pack(anchor="w")
    if nxt:
        fam, goal, _v = nxt
        dash._lbl(box, t("panelLogro", name=t("logro_" + fam, n=goal)), "muted").pack(anchor="w")
    else:
        dash._lbl(box, t("logroCompleto"), "muted").pack(anchor="w")
    bar = tk.Canvas(card.body, height=8, bg=ui.SURFACE, highlightthickness=0, bd=0)
    bar.pack(fill="x", pady=(14, 0))

    def draw(_e=None):
        bar.delete("all")
        w = bar.winfo_width()
        if w < 20:
            return
        ui.round_rect(bar, 0, 0, w, 8, 4, fill=ui.LINE, outline=ui.LINE)
        if got:
            ui.round_rect(bar, 0, 0, max(8, w * got / total), 8, 4, fill=ui.ACCENT, outline=ui.ACCENT)
    bar.bind("<Configure>", draw)


def _section(dash, parent, sec, rows, unlocked):
    card = ui.Card(parent, pad=18)
    card.pack(fill="x", pady=(0, 14))
    first = True
    for fam, value, goals, nxt in rows:
        if not first:
            tk.Frame(card.body, bg=ui.LINE, height=1).pack(fill="x", pady=(10, 12))
        head = tk.Frame(card.body, bg=ui.SURFACE)
        head.pack(fill="x")
        dash._lbl(head, t("logroSec_" + sec) if first else t("logroFam_" + fam), "title" if first else "bold").pack(side="left")
        if first and len(rows) > 1:
            dash._lbl(head, "· " + t("logroFam_" + fam), "muted").pack(side="left", padx=(8, 0))
        dash._lbl(head, fmt_value(fam, value), "bold").pack(side="right")
        sub = (t("logroSiguiente", meta=fmt_goal(fam, nxt)) if nxt is not None else t("logroCompleto"))
        dash._lbl(card.body, sub, "muted").pack(fill="x", pady=(2, 4))
        Timeline(card.body, fam, value, goals,
                 lambda g, fam=fam: share_gui.open_share(dash, "achievement", achievement=(fam, g))).pack(fill="x")
        first = False


def build(dash, parent):
    """Dibuja el resumen y las cuatro secciones dentro de `parent` (un Frame que se vacía y rehace)."""
    for w in parent.winfo_children():
        w.destroy()
    tot = insights.totals(dash.log or [], tasks.done_by_date(tasks.load()))
    _summary(dash, parent, tot)
    for sec, rows in trophies.progress(tot):
        _section(dash, parent, sec, rows, None)
