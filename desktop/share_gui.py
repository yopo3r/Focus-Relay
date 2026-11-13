"""Diálogo "Compartir mi progreso": genera una imagen (racha, resumen o logro) y la guarda como PNG."""
import base64
import random
import tkinter as tk
from datetime import date
from tkinter import filedialog

import i18n
import insights
import share_img
import stats
import tasks
import ui
from i18n import t


def palette():
    return {"A": ui.HERO_A, "B": ui.HERO_B, "C": ui.HERO_C, "FG": ui.HERO_FG}


def period_label(kind, start, end):
    if kind == "day":
        return _date(start)
    if kind == "week":
        return f"{_date(start)} – {_date(end)}"
    if kind == "month":
        return i18n.month_label(start.year, start.month)
    if kind == "year":
        return str(start.year)
    return f"{_date(start)} – {_date(end)}"


def _date(d):
    if i18n.language() in ("zh", "ja", "ko"):
        return i18n.date_label(d)
    if i18n.language() in ("de", "ru"):
        return f"{d.day:02d}.{d.month:02d}.{d.year}"
    return f"{d.day}/{d.month}/{d.year}"


def build_data(kind, log, tdata, period="week", anchor=None, achievement=None):
    """Datos (solo cifras generales) para share_img.render según el tipo de imagen."""
    today = date.today()
    by_date = tasks.done_by_date(tdata)
    tot = insights.totals(log, by_date, today)
    if kind == "streak":
        counts = stats.calendar_counts([s for s in log if insights.is_focus(s)], today)
        return {"streak": tot["streak"], "best": tot["best_streak"], "hours": tot["hours"],
                "last7": insights.last_days(counts, 7, today)}
    if kind == "summary":
        ps = insights.period_stats(log, period, anchor or today, by_date, today)
        return {"kind": period, "label": period_label(period, ps["start"], ps["end"]), "focus_s": ps["focus_s"],
                "sessions": ps["sessions"], "active_days": ps["active_days"], "buckets": ps["buckets"],
                "streak": tot["streak"], "tasks_done": ps["tasks_done"], "rate": ps["rate"]}
    fam, goal = achievement
    return {"family": fam, "goal": goal, "title": t("logro_" + fam, n=goal)}


def unlocked_list(log, tdata):
    tot = insights.totals(log, tasks.done_by_date(tdata))
    return [a for a in insights.achievements(tot) if a["unlocked"]]


def open_share(dash, kind="streak", period="week", anchor=None, achievement=None):
    log, tdata = dash.log, tasks.load()
    unlocked = unlocked_list(log, tdata)
    if kind == "achievement" and achievement is None and unlocked:
        a = unlocked[-1]
        achievement = (a["family"], a["goal"])
    st = {"kind": kind, "size": "square", "period": period if period != "all" else "all",
          "ach": achievement, "photo": None, "img": None}
    name_on = tk.BooleanVar(value=bool(dash.cfg.get("user_name", "").strip()))
    msg = random.choice(i18n.get("motivaShare"))       # frase al azar de la lista predefinida (no editable)

    def build(body, close):
        ui.label(body, t("shareTitulo"), kind="title", bg=ui.SURFACE).pack(fill="x")
        ui.label(body, t("sharePrivacidad"), kind="muted", bg=ui.SURFACE, wraplength=690).pack(fill="x", pady=(2, 10))
        row = tk.Frame(body, bg=ui.SURFACE)
        row.pack(fill="x")
        left = tk.Frame(row, bg=ui.SURFACE)
        left.pack(side="left", fill="y", padx=(0, 16))
        preview = tk.Label(left, bg=ui.SURFACE, bd=0)
        preview.pack()
        right = tk.Frame(row, bg=ui.SURFACE)
        right.pack(side="left", fill="both", expand=True)

        def field(title):
            ui.label(right, title, kind="muted", bg=ui.SURFACE).pack(fill="x", pady=(8, 3))

        def render():
            if st["kind"] == "achievement" and not st["ach"]:
                preview.configure(image="", text=t("shareSinLogros"), fg=ui.MUTED, font=ui.F("body"),
                                  wraplength=220, width=26, height=8)
                st["img"] = None
                return
            data = build_data(st["kind"], log, tdata, st["period"], None, st["ach"])
            name = dash.cfg.get("user_name", "").strip() if name_on.get() else ""
            img = share_img.render(st["kind"], st["size"], palette(), data, name, msg)
            st["img"] = img
            png = share_img.to_png_bytes(img, max_side=400)
            st["photo"] = tk.PhotoImage(data=base64.b64encode(png).decode())
            preview.configure(image=st["photo"], text="", width=0, height=0)

        kinds = [("streak", t("shareRacha")), ("summary", t("shareResumen")), ("achievement", t("shareLogro"))]
        seg_kind = ui.Segmented(right, kinds, st["kind"], lambda k: (st.update(kind=k), sync(), render()),
                                padx=12, pady=6)
        seg_kind.pack(anchor="w")

        periods_box = tk.Frame(right, bg=ui.SURFACE)
        pk = [(k, t(x)) for k, x in zip(insights.KINDS, ("statDia", "statSemana", "statMes", "statAnio", "statTodo"))]
        ui.Segmented(periods_box, pk, st["period"], lambda k: (st.update(period=k), render()), padx=9, pady=5).pack(anchor="w")

        ach_box = tk.Frame(right, bg=ui.SURFACE)
        labels = {t("logro_" + a["family"], n=a["goal"]): (a["family"], a["goal"]) for a in unlocked}
        ach_var = tk.StringVar(value=t("logro_" + st["ach"][0], n=st["ach"][1]) if st["ach"] else "")
        if labels:
            cb = ui.combobox(ach_box, ach_var, list(labels))
            cb.pack(fill="x")
            cb.bind("<<ComboboxSelected>>", lambda e: (st.update(ach=labels[ach_var.get()]), render()))

        def sync():
            periods_box.pack_forget()
            ach_box.pack_forget()
            if st["kind"] == "summary":
                periods_box.pack(anchor="w", pady=(8, 0), after=seg_kind)
            elif st["kind"] == "achievement" and labels:
                ach_box.pack(fill="x", pady=(8, 0), after=seg_kind)

        field(t("shareCuadrada") + " / " + t("shareVertical"))
        ui.Segmented(right, [("square", t("shareCuadrada")), ("story", t("shareVertical"))], st["size"],
                     lambda k: (st.update(size=k), render()), padx=12, pady=6).pack(anchor="w")
        ui.checkbutton(right, t("shareMostrarNombre"), name_on, command=render, bg=ui.SURFACE).pack(fill="x", pady=(10, 0))
        note = ui.label(body, "", kind="muted", bg=ui.SURFACE, wraplength=690)

        def save():
            if st["img"] is None:
                return
            stamp = date.today().isoformat()
            path = filedialog.asksaveasfilename(
                parent=body.winfo_toplevel(), defaultextension=".png", initialfile=f"focus-{st['kind']}-{stamp}.png",
                filetypes=[("PNG", "*.png")])
            if path:
                st["img"].save(path, "PNG", optimize=True)
                note.configure(text=t("shareGuardada", p=path), fg=ui.SUCCESS_FG)

        bar = tk.Frame(body, bg=ui.SURFACE)
        bar.pack(fill="x", pady=(14, 0))
        ui.Button(bar, t("shareGuardar"), save, style="primary").pack(side="right")
        ui.Button(bar, t("cerrar"), lambda: close(None), style="ghost").pack(side="right", padx=(0, 8))
        note.pack(fill="x", pady=(8, 0))
        sync()
        render()

    ui._modal(dash.top, t("shareTitulo"), build, width=740)
