"""Ventana "Mi agenda": lo que viene en los próximos días en un solo lugar.

Reúne (1) tareas pendientes, con las automáticas de los días siguientes, (2) eventos del calendario
sincronizado/importado y eventos manuales, y (3) las sesiones sugeridas que el usuario agregó.
"""
import os
import tkinter as tk
from datetime import date, datetime, timedelta

import calendar_planner as cp
import i18n
import manual_events as me
import tasks
import ui
from config import calendar_path, load_config
from i18n import t

DAYS = 14
_win = {"top": None}


def _day_label(d, today):
    names = i18n.get("diasSemanaCorto")
    base = f"{names[d.weekday()]} {d.day:02d}/{d.month:02d}"
    if d == today:
        return f"{t('agendaHoy')} · {base}"
    if d == today + timedelta(days=1):
        return f"{t('agendaManana')} · {base}"
    return base


def collect(now=None):
    """{fecha: [(hora|None, tipo, título, detalle)]} para los próximos DAYS días, más las tareas de hoy sin hacer."""
    now = now or datetime.now()
    today = now.date()
    cfg = load_config()
    days = {today + timedelta(days=i): [] for i in range(DAYS)}

    # eventos del calendario sincronizado/importado + manuales
    events = []
    try:
        if os.path.exists(calendar_path()):
            with open(calendar_path(), encoding="utf-8", errors="replace") as f:
                events = cp.load_events(f.read(), datetime.combine(today, datetime.min.time()),
                                        datetime.combine(today + timedelta(days=DAYS), datetime.min.time()))
    except Exception:
        events = []
    events += me.to_events(cfg.get("manual_events", []))
    for e in events:
        d = e.start.date()
        if d in days and (d > today or e.end > now - timedelta(hours=1)):
            when = None if getattr(e, "all_day", False) else e.start
            detail = t("agendaTodoDia") if when is None else f"{e.start:%H:%M} – {e.end:%H:%M}"
            days[d].append((when, "event", e.summary, detail))

    # sesiones sugeridas agregadas por el usuario
    for s in cfg.get("planned_sessions", []):
        try:
            start = datetime.strptime(s["start"], "%Y-%m-%dT%H:%M")
        except (KeyError, ValueError, TypeError):
            continue
        d = start.date()
        if d in days and start + timedelta(minutes=int(s.get("minutes", 0))) > now - timedelta(hours=1):
            end = start + timedelta(minutes=int(s.get("minutes", 0)))
            days[d].append((start, "session", s.get("title", "?"), f"{start:%H:%M} – {end:%H:%M} · {s.get('minutes', 0)} min"))

    # tareas automáticas de los días que vienen (las de hoy ya están en la lista)
    data = tasks.load()
    for tpl in data.get("templates", []):
        if not tpl.get("active", True):
            continue
        for d in days:
            if d > today and d.weekday() in tpl.get("days", []):
                days[d].append((None, "auto", tpl.get("text", "?"), t("agendaAuto")))
    for d in days:
        days[d].sort(key=lambda x: (x[0] is None, x[0] or datetime.min, x[2]))
    return days


def open_agenda(dash):
    top = _win["top"]
    if top is not None:
        try:
            if top.winfo_exists():
                top.deiconify()
                top.lift()
                return
        except tk.TclError:
            pass
    ui.refresh_theme()
    win, hero, content = ui.make_window(dash.top, "Focus Relay Desktop · " + t("agendaTitulo"), "720x760",
                                        t("agendaTitulo"), minsize=(560, 500))
    _win["top"] = win
    content.pack_forget()
    content.pack(fill="both", expand=True, padx=18, pady=(14, 14))
    ui.label(content, t("agendaResumen", n=DAYS), kind="muted", bg=ui.CANVAS, wraplength=640).pack(fill="x", pady=(0, 10))
    sf = ui.ScrollFrame(content)
    sf.pack(fill="both", expand=True)
    holder = sf.inner

    def render():
        for w in holder.winfo_children():
            w.destroy()
        today = date.today()
        # --- tareas pendientes
        data = tasks.load()
        if tasks.roll(data):
            tasks.save(data)
        pending = [i for i in tasks.today_items(data) if not i.get("done")]
        card = ui.Card(holder, pad=14, radius=14)
        card.pack(fill="x", pady=(0, 12), padx=1)
        head = tk.Frame(card.body, bg=ui.SURFACE)
        head.pack(fill="x")
        ui.label(head, t("agendaPendientes") + (f" ({len(pending)})" if pending else ""), kind="title",
                 bg=ui.SURFACE).pack(side="left")
        ui.Button(head, t("agendaIrTareas"), go_tasks, style="ghost", padx=10, pady=4).pack(side="right")
        if not pending:
            ui.label(card.body, t("agendaSinPend"), kind="muted", bg=ui.SURFACE).pack(fill="x", pady=(8, 0))
        for item in pending:
            row = tk.Frame(card.body, bg=ui.SURFACE)
            row.pack(fill="x", pady=(8, 0))
            var = tk.BooleanVar(value=False)
            ui.checkbutton(row, item["text"], var, command=lambda i=item, v=var: toggle(i, v), bg=ui.SURFACE
                           ).pack(side="left", fill="x", expand=True)
            if item.get("carried_from"):
                ui.Pill(row, t("agendaAtrasada"), ui.MUTED, ui.TAG_BG).pack(side="right")
        # --- línea de tiempo
        days = collect()
        for d, items in days.items():
            ui.label(holder, _day_label(d, today), kind="eyebrow", bg=ui.CANVAS).pack(fill="x", pady=(8, 4), padx=2)
            if not items:
                ui.label(holder, t("agendaVacioDia"), kind="muted", bg=ui.CANVAS).pack(fill="x", padx=8)
                continue
            for when, kind, title, detail in items:
                add_row(kind, title, detail)

    def add_row(kind, title, detail):
        colors = {"event": (ui.MODE_T if hasattr(ui, "MODE_T") else ui.PRIMARY, "agendaEvento"),
                  "session": (ui.SUCCESS, "agendaSesion"), "auto": (ui.ACCENT, "agendaAuto")}
        accent, label_key = colors[kind]
        row = tk.Frame(holder, bg=ui.SURFACE, highlightthickness=1, highlightbackground=ui.LINE)
        row.pack(fill="x", pady=(0, 6), padx=1)
        tk.Frame(row, bg=accent, width=4).pack(side="left", fill="y")
        mid = tk.Frame(row, bg=ui.SURFACE)
        mid.pack(side="left", fill="x", expand=True, padx=12, pady=8)
        tk.Label(mid, text=title, font=ui.F("bold"), fg=ui.INK, bg=ui.SURFACE, anchor="w", justify="left",
                 wraplength=420).pack(fill="x")
        tk.Label(mid, text=detail, font=ui.F("small"), fg=ui.MUTED, bg=ui.SURFACE, anchor="w").pack(fill="x")
        ui.Pill(row, t(label_key), accent, ui.mix(ui.SURFACE, accent, 0.14)).pack(side="right", padx=12)

    def toggle(item, var):
        data = tasks.load()
        tasks.set_done(data, item["id"], True, date.today())
        tasks.save(data)
        dash.tasks_changed()
        page = getattr(dash, "tasks_page", None)
        if page:
            page.refresh()
        render()

    def go_tasks():
        win.destroy()
        dash.tabs.set("tareas")
        dash._show_tab("tareas")

    bar = tk.Frame(win, bg=ui.CANVAS)
    bar.pack(side="bottom", fill="x", padx=18, pady=(0, 14))
    import calendar_gui
    ui.Button(bar, t("agendaAbrirSesiones"), lambda: calendar_gui.open_calendar_window(dash.top), style="ghost"
              ).pack(side="left")
    ui.Button(bar, t("cerrar"), win.destroy, style="primary").pack(side="right")
    render()
