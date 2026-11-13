"""Pestaña "Estadísticas": período (día/semana/mes/año/todo), gráfico, desglose y logros."""
import tkinter as tk
from datetime import date

import i18n
import insights
import share_gui
import stats
import tasks
import ui
from i18n import t

KIND_KEYS = ("statDia", "statSemana", "statMes", "statAnio", "statTodo")
FAMILY_ORDER = [f[0] for f in insights.FAMILIES]


def _bucket_label(kind, label):
    if kind == "week":
        return i18n.get("diasSemanaCorto")[label]
    if kind == "year":
        name = i18n.MONTHS[i18n.language()][label]
        return name if i18n.language() in ("zh", "ja", "ko") else name[:3]
    return str(label)


class StatsPage:
    def __init__(self, dash, parent):
        self.d = dash
        self.kind = "week"
        self.anchor = date.today()
        self.tip = None
        self.cells = []
        # --- barra superior
        bar = tk.Frame(parent, bg=ui.CANVAS)
        bar.pack(fill="x", pady=(0, 12))
        self.seg = ui.Segmented(bar, list(zip(insights.KINDS, [t(k) for k in KIND_KEYS])), self.kind, self._set_kind,
                                padx=14, pady=6)
        self.seg.pack(side="left")
        ui.Button(bar, t("compartir"), self._share, style="primary", pady=7).pack(side="right")
        self.nav = tk.Frame(parent, bg=ui.CANVAS)
        self.nav.pack(fill="x", pady=(0, 12))
        self.prev_btn = ui.Button(self.nav, "‹", lambda: self._move(-1), style="ghost", padx=14, pady=5)
        self.prev_btn.pack(side="left")
        self.next_btn = ui.Button(self.nav, "›", lambda: self._move(1), style="ghost", padx=14, pady=5)
        self.next_btn.pack(side="right")
        self.period_lbl = ui.label(self.nav, "", kind="title", bg=ui.CANVAS)
        self.period_lbl.configure(anchor="center")
        self.period_lbl.pack(side="left", expand=True, fill="x")
        # --- cifras principales (las demás quedan en «Más detalles»)
        self.kpis = tk.Frame(parent, bg=ui.CANVAS)
        self.kpis.pack(fill="x")
        # --- gráfico
        self.chart_card = d_card = dash._card(parent, t("statGrafico"))
        d_card.pack(fill="x", pady=(4, 0))
        self.delta_lbl = dash._lbl(d_card.body, "", "muted")
        self.delta_lbl.pack(fill="x")
        self.canvas = tk.Canvas(d_card.body, bg=ui.SURFACE, highlightthickness=0, bd=0, height=200)
        self.canvas.pack(fill="x", pady=(6, 0))
        self.canvas.bind("<Configure>", lambda e: self._paint_chart())
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Leave>", lambda e: self.tip_lbl.configure(text=""))
        self.tip_lbl = dash._lbl(d_card.body, "", "muted")
        self.tip_lbl.pack(fill="x", pady=(4, 0))
        # --- racha en una sola línea
        self.ach_card = dash._card(parent)
        self.ach_card.pack(fill="x", pady=(14, 0))
        # --- detalles plegados: cifras extra y desglose por modo / etiqueta
        self.more_open = False
        self.more_btn = ui.Button(parent, "▸  " + t("statMasDetalles"), self._toggle_more, style="ghost", pady=6)
        self.more_btn.pack(anchor="w", pady=(14, 0))
        self.more = tk.Frame(parent, bg=ui.CANVAS)
        self.more_kpis = tk.Frame(self.more, bg=ui.CANVAS)
        self.more_kpis.pack(fill="x", pady=(10, 0))
        self.split = tk.Frame(self.more, bg=ui.CANVAS)
        self.split.pack(fill="x", pady=(4, 0))
        self.split.columnconfigure(0, weight=1, uniform="s")
        self.split.columnconfigure(1, weight=1, uniform="s")
        self.mode_card = dash._card(self.split, t("statPorModo"))
        self.mode_card.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.tag_card = dash._card(self.split, t("statPorEtiqueta"))
        self.tag_card.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self.refresh()

    def _toggle_more(self):
        self.more_open = not self.more_open
        self.more_btn.configure(text=("▾  " + t("statMenosDetalles")) if self.more_open else ("▸  " + t("statMasDetalles")))
        if self.more_open:
            self.more.pack(fill="x", after=self.more_btn)
        else:
            self.more.pack_forget()

    # ------------------------------------------------------------ acciones
    def _set_kind(self, k):
        self.kind = k
        self.anchor = date.today()
        self.refresh()

    def _move(self, n):
        self.anchor = insights.shift(self.kind, self.anchor, n)
        self.refresh()

    def _share(self):
        share_gui.open_share(self.d, "summary", period=self.kind, anchor=self.anchor)

    # ------------------------------------------------------------ pintar
    def refresh(self):
        log, today = self.d.log, date.today()
        self.by_date = tasks.done_by_date(tasks.load())
        self.ps = ps = insights.period_stats(log, self.kind, self.anchor, self.by_date, today)
        self.tot = insights.totals(log, self.by_date, today)
        label = share_gui.period_label(self.kind, ps["start"], ps["end"])
        if self.kind == "week":
            label = t("statSemana") + " · " + label
        elif self.kind == "all":
            label = t("statTodo")
        self.period_lbl.configure(text=label)
        nav_on = self.kind != "all"
        for b in (self.prev_btn, self.next_btn):
            b.pack_forget()
        if nav_on:
            self.prev_btn.pack(side="left")
            self.next_btn.pack(side="right")
            self.period_lbl.pack_forget()
            self.period_lbl.pack(side="left", expand=True, fill="x")
        self._paint_kpis()
        self._paint_delta()
        self._paint_chart()
        self._paint_split()
        self._paint_streak()

    def _paint_kpis(self):
        ps = self.ps
        best = ps["best_day"]
        main = [
            (t("statTiempo"), stats.fmt_long(ps["focus_s"])),
            (t("statSesiones"), str(ps["sessions"])),
            (t("statDiasActivos"), str(ps["active_days"])),
        ]
        extra = [
            (t("statTasa"), f"{ps['rate']}%" if ps["rate"] is not None else "–"),
            (t("statPromedio"), stats.fmt_long(ps["avg_s"])),
            (t("statMasLarga"), stats.fmt_long(ps["longest_s"])),
            (t("statMejorDia"), f"{share_gui._date(best[0])}\n{stats.fmt_long(best[1])}" if best else "–"),
            (t("statTareas"), str(ps["tasks_done"])),
        ]
        self._kpi_grid(self.kpis, main, 3)
        self._kpi_grid(self.more_kpis, extra, 5)

    def _kpi_grid(self, host, items, cols):
        for w in host.winfo_children():
            w.destroy()
        for c in range(cols):
            host.columnconfigure(c, weight=1, uniform="k")
        for i, (lab, val) in enumerate(items):
            card = ui.Card(host, pad=12)
            card.grid(row=i // cols, column=i % cols, sticky="nsew",
                      padx=(0 if i % cols == 0 else 5, 0 if i % cols == cols - 1 else 5), pady=(0, 10))
            self.d._lbl(card.body, lab, "muted").pack(fill="x")
            small = "\n" in val
            tk.Label(card.body, text=val, bg=ui.SURFACE, fg=ui.ACCENT, anchor="w", justify="left",
                     font=ui.F("bold" if small else "h1")).pack(fill="x", pady=(4, 0))

    def _paint_delta(self):
        ps = self.ps
        txt = ""
        if ps["prev"] is not None:
            p = insights.delta_pct(ps["focus_s"], ps["prev"]["focus_s"])
            if p is not None:
                txt = t("statVsAnterior", p=f"{'+' if p > 0 else ''}{p}%")
        self.delta_lbl.configure(text=txt)

    def _paint_chart(self):
        c = self.canvas
        c.delete("all")
        self.cells = []
        w = max(c.winfo_width(), 300)
        h = int(c["height"])
        buckets = self.ps["buckets"]
        if not any(b[1] for b in buckets):
            c.create_text(w / 2, h / 2, text=t("statSinDatos"), fill=ui.MUTED, font=ui.F("body"))
            return
        n = len(buckets)
        top = max(b[1] for b in buckets)
        left, bottom = 8, h - 22
        bw = (w - left * 2) / n
        every = 1 if n <= 14 else (2 if n <= 31 else 4)
        for i, (lab, v, d) in enumerate(buckets):
            x0 = left + i * bw
            bar = max(bw * 0.64, 3)
            bx = x0 + (bw - bar) / 2
            hh = (bottom - 16) * v / top
            if v:
                ui.round_rect(c, bx, bottom - max(hh, 4), bx + bar, bottom, min(bar / 2, 6), fill=ui.PRIMARY, outline=ui.PRIMARY)
            else:
                c.create_rectangle(bx, bottom - 2, bx + bar, bottom, fill=ui.DOT_OFF, outline="")
            if i % every == 0 and self.kind != "day" or (self.kind == "day" and i % 3 == 0):
                c.create_text(x0 + bw / 2, h - 9, text=_bucket_label(self.ps["kind"], lab), fill=ui.MUTED, font=ui.F("small"))
            label = _bucket_label(self.ps["kind"], lab)
            full = (share_gui._date(d) if d and self.kind in ("week", "month") else label)
            self.cells.append((x0, x0 + bw, f"{full}: {stats.fmt_long(v)}"))

    def _hover(self, e):
        for x1, x2, text in self.cells:
            if x1 <= e.x < x2:
                self.tip_lbl.configure(text=text)
                return
        self.tip_lbl.configure(text="")

    def _paint_split(self):
        for card, rows in ((self.mode_card, self._mode_rows()), (self.tag_card, self._tag_rows())):
            for w in card.body.winfo_children()[1:]:
                w.destroy()
            if not rows:
                self.d._lbl(card.body, t("statSinDatos"), "muted", wraplength=300).pack(fill="x")
                continue
            top = max(r[1] for r in rows) or 1
            for name, secs, color in rows:
                line = tk.Frame(card.body, bg=ui.SURFACE)
                line.pack(fill="x", pady=3)
                head = tk.Frame(line, bg=ui.SURFACE)
                head.pack(fill="x")
                self.d._lbl(head, name, "body").pack(side="left")
                self.d._lbl(head, stats.fmt_long(secs), "muted").pack(side="right")
                bar = tk.Canvas(line, height=8, bg=ui.SURFACE, highlightthickness=0, bd=0)
                bar.pack(fill="x", pady=(2, 0))
                bar.bind("<Configure>", lambda e, b=bar, s=secs, c=color, top=top: (
                    b.delete("all"), ui.round_rect(b, 0, 0, e.width, 8, 4, fill=ui.TAG_BG, outline=""),
                    ui.round_rect(b, 0, 0, max(8, e.width * s / top), 8, 4, fill=c, outline="") if s else None))

    def _mode_rows(self):
        bm = self.ps["by_mode"]
        names = {"T": "tipoTemporizador", "C": "tipoCronometro", "P": "tipoPomodoroTrabajo"}
        rows = [(t(names[k]), bm[k], self.d._mc(k)) for k in ("T", "C", "P") if bm[k]]
        return rows

    def _tag_rows(self):
        return [(name or t("statSinEtiqueta"), secs, ui.PRIMARY) for name, secs in [(a, b) for a, b in self._tags()][:6]]

    def _tags(self):
        out = []
        for name, v in self.ps["tags"]:
            secs = v["seconds"] if isinstance(v, dict) else v
            out.append((name, secs))
        return sorted(out, key=lambda x: -x[1])

    def _paint_streak(self):
        """Una sola línea con la racha y el avance de logros; el detalle vive en la pestaña de Logros."""
        body = self.ach_card.body
        for w in body.winfo_children():
            w.destroy()
        tot = self.tot
        ach = insights.achievements(tot)
        got = sum(1 for a in ach if a["unlocked"])
        row = tk.Frame(body, bg=ui.SURFACE)
        row.pack(fill="x")
        self.d._lbl(row, f"{t('statRachaActual')}: {t('statDias', n=tot['streak'])}", "bold").pack(side="left")
        self.d._lbl(row, f"   ·   {t('statLogros')} {t('statLogrosCuenta', a=got, b=len(ach))}", "muted").pack(side="left")
        ui.Button(row, t("shareRacha"), lambda: share_gui.open_share(self.d, "streak"), style="ghost", pady=4).pack(side="right")
        ui.Button(row, t("statLogros"), self.d._open_logros, style="ghost", pady=4).pack(side="right", padx=(0, 8))
