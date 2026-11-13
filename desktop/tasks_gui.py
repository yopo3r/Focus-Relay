"""Pestaña "Tareas": lista del día y tareas automáticas por día de la semana."""
import tkinter as tk
from datetime import date
from tkinter import font as tkfont

import i18n
import stats
import tasks
import ui
from i18n import t


def fmt_date(d, long=False):
    """Fecha corta en el idioma actual ('3 nov 2026')."""
    return i18n.date_label(d, long)


class DayChip(tk.Canvas):
    def __init__(self, parent, letter, on, command, size=28):
        super().__init__(parent, width=size, height=size, bg=ui.SURFACE, highlightthickness=0, bd=0, cursor="hand2")
        self._letter, self._size = letter, size
        self.on = on
        self._paint()
        self.bind("<Button-1>", lambda e: command())

    def _paint(self):
        s = self._size
        self.delete("all")
        self.create_oval(1, 1, s - 1, s - 1, fill=ui.PRIMARY if self.on else ui.TAG_BG, outline=ui.PRIMARY if self.on else ui.LINE)
        self.create_text(s / 2, s / 2, text=self._letter, font=ui.F("small_bold"),
                         fill=ui.ON_PRIMARY if self.on else ui.MUTED)

    def set(self, on):
        self.on = on
        self._paint()


class TasksPage:
    def __init__(self, dash, parent):
        self.d = dash
        self.day = date.today()
        self.data = tasks.load()
        self.new_days = set()
        self.fonts = {
            "done": tkfont.Font(family=ui.F("body")[0], size=ui.F("body")[1], overstrike=True),
            "todo": tkfont.Font(family=ui.F("body")[0], size=ui.F("body")[1]),
        }
        parent.columnconfigure(0, weight=3, uniform="tk")
        parent.columnconfigure(1, weight=2, uniform="tk")
        left = tk.Frame(parent, bg=ui.CANVAS)
        left.grid(row=0, column=0, sticky="new", padx=(0, 7))
        right = tk.Frame(parent, bg=ui.CANVAS)
        right.grid(row=0, column=1, sticky="new", padx=(7, 0))
        self._build_today(left)
        self._build_auto(right)
        self.refresh()

    # ------------------------------------------------------------ hoy
    def _build_today(self, parent):
        card = self.d._card(parent, t("tareasHoy"))
        card.pack(fill="x")
        b = card.body
        self.date_lbl = self.d._lbl(b, "", "muted")
        self.date_lbl.pack(fill="x")
        self.bar = tk.Canvas(b, height=12, bg=ui.SURFACE, highlightthickness=0, bd=0)
        self.bar.pack(fill="x", pady=(8, 2))
        self.bar.bind("<Configure>", lambda e: self._paint_bar())
        self.prog_lbl = self.d._lbl(b, "", "bold")
        self.prog_lbl.pack(fill="x", pady=(2, 10))
        row = tk.Frame(b, bg=ui.SURFACE)
        row.pack(fill="x")
        self.new_var = tk.StringVar()
        e = ui.entry(row, self.new_var)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self._add())
        self.entry = e
        ui.Button(row, t("agregarTarea"), self._add, style="primary", pady=7).pack(side="left", padx=(8, 0))
        self.hint = self.d._lbl(b, t("tareaNueva"), "muted")
        self.hint.pack(fill="x", pady=(4, 8))
        self.list = tk.Frame(b, bg=ui.SURFACE)
        self.list.pack(fill="x")

    def _paint_bar(self):
        c = self.bar
        w = max(c.winfo_width(), 50)
        c.delete("all")
        ui.round_rect(c, 0, 0, w, 12, 6, fill=ui.TAG_BG, outline="")
        done, total = tasks.progress(self.data, self.day)
        if total and done:
            ui.round_rect(c, 0, 0, max(12, w * done / total), 12, 6, fill=ui.SUCCESS if done == total else ui.PRIMARY, outline="")

    def _add(self):
        item = tasks.add_task(self.data, self.new_var.get(), self.day)
        if item:
            tasks.save(self.data)
        self.new_var.set("")
        self.refresh()
        self.entry.focus_set()

    def _toggle(self, item_id, done):
        tasks.set_done(self.data, item_id, done, self.day)
        tasks.save(self.data)
        self.refresh()
        self.d.tasks_changed()

    def _start(self, item):
        if not self.d.start_task(item["text"]):
            self.hint.configure(text=t("tareaOcupada"), fg=ui.DANGER)

    def _delete(self, item_id):
        tasks.delete_task(self.data, item_id)
        tasks.save(self.data)
        self.refresh()

    def _row(self, item):
        row = tk.Frame(self.list, bg=ui.SURFACE)
        row.pack(fill="x", pady=3)
        chk = tk.Canvas(row, width=28, height=28, bg=ui.SURFACE, highlightthickness=0, bd=0, cursor="hand2")
        chk.pack(side="left", padx=(0, 10))
        if item["done"]:
            chk.create_oval(2, 2, 26, 26, fill=ui.SUCCESS, outline=ui.SUCCESS)
            chk.create_line(8, 14, 12.5, 19, 20, 9, fill="#ffffff", width=2.5, capstyle="round", joinstyle="round")
        else:
            chk.create_oval(2, 2, 26, 26, outline=ui.CTRL_BORDER, width=2)
        chk.bind("<Button-1>", lambda e, i=item: self._toggle(i["id"], not i["done"]))
        x = tk.Label(row, text="✕", bg=ui.SURFACE, fg=ui.MUTED, cursor="hand2", padx=6)
        x.pack(side="right")
        x.bind("<Button-1>", lambda e, i=item: self._delete(i["id"]))
        if not item["done"] and self.day == date.today():
            play = tk.Label(row, text="▶", bg=ui.SURFACE, fg=ui.PRIMARY, cursor="hand2", padx=8)
            play.pack(side="right")
            play.bind("<Button-1>", lambda e, i=item: self._start(i))
        box = tk.Frame(row, bg=ui.SURFACE)
        box.pack(side="left", fill="x", expand=True)
        lbl = tk.Label(box, text=item["text"], bg=ui.SURFACE, fg=ui.MUTED if item["done"] else ui.INK,
                       font=self.fonts["done" if item["done"] else "todo"], anchor="w", justify="left", wraplength=420,
                       cursor="hand2")
        lbl.pack(fill="x")
        lbl.bind("<Button-1>", lambda e, i=item: self._toggle(i["id"], not i["done"]))
        spent = self.d.task_seconds(item)
        if spent >= 60:
            tk.Label(box, text=t("tareaTiempo", m=stats.fmt_long(spent)), bg=ui.SURFACE, fg=ui.MUTED,
                     font=ui.F("tiny"), anchor="w").pack(fill="x")
        if item.get("carried_from") and not item["done"]:
            tk.Label(box, text=t("tareaArrastrada"), bg=ui.SURFACE, fg=ui.DANGER, font=ui.F("tiny"), anchor="w").pack(fill="x")

    # ------------------------------------------------------------ automáticas
    def _build_auto(self, parent):
        card = self.d._card(parent, t("tareasAutoTitulo"), info=t("tareasAutoAviso"))
        card.pack(fill="x")
        b = card.body
        self.auto_var = tk.StringVar()
        e = ui.entry(b, self.auto_var)
        e.pack(fill="x")
        e.bind("<Return>", lambda ev: self._add_template())
        self.d._lbl(b, t("tareaAutoNombre"), "muted").pack(fill="x", pady=(4, 8))
        days = tk.Frame(b, bg=ui.SURFACE)
        days.pack(fill="x")
        self.new_chips = []
        letters = i18n.get("diasSemanaCorto")
        for i in range(7):
            chip = DayChip(days, letters[i], False, lambda i=i: self._toggle_new_day(i))
            chip.pack(side="left", padx=(0, 6))
            self.new_chips.append(chip)
        ui.Button(b, t("tareaAutoAgregar"), self._add_template, style="ghost", pady=7).pack(anchor="w", pady=(10, 0))
        self.auto_notice = ui.Notice(b, "error")
        self.auto_notice.pack(fill="x", pady=(8, 0))
        self.tpl_list = tk.Frame(b, bg=ui.SURFACE)
        self.tpl_list.pack(fill="x", pady=(8, 0))

    def _toggle_new_day(self, i):
        self.new_days.symmetric_difference_update({i})
        self.new_chips[i].set(i in self.new_days)

    def _add_template(self):
        if not self.new_days:
            self.auto_notice.set(t("tareaAutoSinDias"), "error")
            return
        tpl = tasks.add_template(self.data, self.auto_var.get(), self.new_days)
        if not tpl:
            return
        tasks.roll(self.data, self.day)           # si hoy toca, aparece de inmediato
        tasks.save(self.data)
        self.auto_var.set("")
        self.new_days.clear()
        for c in self.new_chips:
            c.set(False)
        self.auto_notice.set("", "success")
        self.refresh()

    def _toggle_tpl_day(self, tid, i):
        tasks.toggle_template_day(self.data, tid, i)
        tasks.save(self.data)
        self._render_templates()

    def _delete_tpl(self, tid):
        tasks.delete_template(self.data, tid, True, self.day)
        tasks.save(self.data)
        self.refresh()

    def _render_templates(self):
        for w in self.tpl_list.winfo_children():
            w.destroy()
        if not self.data["templates"]:
            self.d._lbl(self.tpl_list, t("tareaAutoVacio"), "muted").pack(fill="x")
            return
        letters = i18n.get("diasSemanaCorto")
        for tpl in self.data["templates"]:
            box = tk.Frame(self.tpl_list, bg=ui.TAG_BG)
            box.pack(fill="x", pady=3)
            top = tk.Frame(box, bg=ui.TAG_BG)
            top.pack(fill="x", padx=10, pady=(8, 4))
            tk.Label(top, text=tpl["text"], bg=ui.TAG_BG, fg=ui.INK, font=ui.F("bold"), anchor="w", justify="left",
                     wraplength=240).pack(side="left", fill="x", expand=True)
            x = tk.Label(top, text="✕", bg=ui.TAG_BG, fg=ui.MUTED, cursor="hand2", padx=4)
            x.pack(side="right")
            x.bind("<Button-1>", lambda e, i=tpl["id"]: self._delete_tpl(i))
            chips = tk.Frame(box, bg=ui.TAG_BG)
            chips.pack(fill="x", padx=10, pady=(0, 8))
            for i in range(7):
                c = DayChip(chips, letters[i], i in tpl["days"], lambda i=i, tid=tpl["id"]: self._toggle_tpl_day(tid, i), size=26)
                c.configure(bg=ui.TAG_BG)
                c._paint()
                c.pack(side="left", padx=(0, 5))

    # ------------------------------------------------------------ pintar
    def refresh(self):
        self.day = date.today()
        if tasks.roll(self.data, self.day):
            tasks.save(self.data)
        self.date_lbl.configure(text=fmt_date(self.day, long=True))
        for w in self.list.winfo_children():
            w.destroy()
        items = tasks.today_items(self.data, self.day)
        done, total = tasks.progress(self.data, self.day)
        self.prog_lbl.configure(text=t("tareasProgreso", a=done, b=total) if total else "")
        if not items:
            self.d._lbl(self.list, t("tareasVacio"), "muted").pack(fill="x", pady=8)
        else:
            for it in items:
                self._row(it)
            if done == total:
                tk.Label(self.list, text=t("tareasTodoListo"), bg=ui.SUCCESS_BG, fg=ui.SUCCESS_FG, font=ui.F("bold"),
                         anchor="w", padx=12, pady=10).pack(fill="x", pady=(10, 0))
        self._paint_bar()
        self._render_templates()
        self.d.tasks_changed()
