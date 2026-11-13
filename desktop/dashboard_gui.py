"""Panel principal de Focus Relay Desktop.

Reúne todo lo que antes mostraba la página web del ESP-01S (reloj en vivo, calendario,
historial, etiquetas, frases, ajustes del dispositivo, idiomas, colores) y suma música y
premios. Los datos de sesiones siguen guardados en el ESP-01S; el resto vive en config.json.
"""
import math
import os
import random
import threading
import time
import tkinter as tk
from datetime import date, datetime
from tkinter import colorchooser, filedialog, ttk

import emoji_img
import esp_client
import guard
import ring_img
import i18n
import music
import rewards
import stats
import ui
from config import load_config, load_data, update_config
from i18n import t

_open = {"top": None}
TABS = ["panel", "tareas", "stats", "hist", "premios", "ajustes", "ayuda", "acerca"]
MODE_NAME_KEY = {"T": "tipoTemporizador", "C": "tipoCronometro", "W": "tipoPomodoroTrabajo", "D": "tipoPomodoroDescanso"}


def run_async(widget, func, callback=None):
    """Ejecuta `func` en un hilo y entrega (ok, resultado) a `callback` en el hilo de la interfaz."""
    box = {}

    def work():
        try:
            box["r"] = (True, func())
        except Exception as exc:
            box["r"] = (False, exc)

    threading.Thread(target=work, daemon=True).start()

    def poll():
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        if "r" not in box:
            widget.after(80, poll)
            return
        if callback:
            callback(*box["r"])

    poll()


def open_dashboard(root, shared_state, state_lock, tab=None):
    existing = _open["top"]
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_force()
        return
    Dashboard(root, shared_state, state_lock, tab or "panel")


def rebuild(root, shared_state, state_lock, tab):
    """Los widgets conservan sus colores/idioma: al cambiar tema o idioma se vuelve a crear todo."""
    _open["top"] = None
    for child in list(root.winfo_children()):
        if isinstance(child, tk.Toplevel):
            child.destroy()
    root.after(60, lambda: open_dashboard(root, shared_state, state_lock, tab))


def mode_name(code):
    if code == "P":
        code = "W"
    return t(MODE_NAME_KEY.get(code, "tipoTemporizador")) if code in MODE_NAME_KEY else str(code)


class Dashboard:
    def __init__(self, root, shared_state, state_lock, tab):
        self.root, self.state, self.lock = root, shared_state, state_lock
        ui.refresh_theme()
        self.cfg = load_config()
        i18n.set_language(self.cfg.get("language", "es"))
        self.log, self.log_loaded, self.log_time = [], False, None
        self.month = date.today().replace(day=1)
        self.show_all = False
        self.tab = tab if tab in TABS else "panel"
        self.photos = []          # referencias a imágenes (si no, Tk las descarta)
        self.live = {}
        self.estado_shown = None
        with self.lock:
            self._celebrate_seen = self.state.get("celebrate", 0)     # no repetir celebraciones anteriores
            self.state["won"] = []
        self._cele_wait, self._won_buf = None, []                     # celebración a la espera de su trofeo

        self.top, self.hero, self.body = ui.make_window(
            root, "Focus Relay Desktop", "1180x820", self._greeting(), minsize=(1060, 700),
            eyebrow="FOCUS RELAY DESKTOP", hero_h=84)
        _open["top"] = self.top
        self.top.protocol("WM_DELETE_WINDOW", self._close)

        self.body.pack_forget()
        nav = tk.Frame(self.top, bg=ui.CANVAS)
        nav.pack(fill="x", padx=18, pady=(14, 0))
        self.tabs = ui.Segmented(nav, [(k, t(self._tab_key(k))) for k in TABS], self.tab, self._on_tab)
        self.tabs.pack(side="left")
        ui.Button(nav, t("btnSugeridas"), self._open_suggestions, style="ghost").pack(side="right")
        ui.Button(nav, t("btnBloqueo"), self._open_block, style="ghost").pack(side="right", padx=(0, 8))

        self.pages_host = tk.Frame(self.top, bg=ui.CANVAS)
        self.pages_host.pack(fill="both", expand=True, padx=18, pady=(12, 14))
        self.pages = {}
        self.built = set()
        self._show_tab(self.tab)

        self._tick()
        self._refresh_log()
        self.top.after(20000, self._periodic_log)
        if not self.cfg.get("tutorial_done"):               # primera vez que se abre la app
            self._save_cfg(tutorial_done=True)
            self.top.after(700, self.show_tutorial)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _tab_key(k):
        return {"panel": "tabPanel", "tareas": "tabTareas", "stats": "tabEstadisticas", "hist": "tabHistorial", "premios": "tabPremios", "acerca": "tabAcerca", "ajustes": "tabAjustes", "ayuda": "tabAyuda"}[k]

    def _greeting(self):
        name = self.cfg.get("user_name", "").strip()
        return t("tituloConNombre", n=name) if name else t("tituloBase")

    def _alive(self):
        try:
            return self.top.winfo_exists()
        except tk.TclError:
            return False

    def _close(self):
        _open["top"] = None
        self.top.destroy()
        with self.lock:
            no_tray = self.state.get("no_tray")
        if no_tray:                       # sin ícono de bandeja no habría forma de volver a abrirla
            self.root.event_generate("<<QuitApp>>")

    def _open_block(self):
        import gui
        gui.open_config_window(self.root, self.state, self.lock)

    def _open_sites(self):
        import sites_gui
        sites_gui.open_sites_window(self.root, self.state, self.lock)

    def _open_suggestions(self):
        from calendar_gui import open_calendar_window
        open_calendar_window(self.root)

    def _save_cfg(self, **changes):
        self.cfg = update_config(**changes)

    def _toggle_streak_day(self, i):
        sel = set(stats.streak_days(self.cfg)) ^ {i}
        if not sel:                                         # al menos un día de trabajo
            return
        self._save_cfg(streak_days=sorted(sel))
        self._streak_chips[i].set(i in sel)
        try:
            self._render_calendar()
        except Exception:
            pass

    def _lbl(self, parent, text, kind="body", bg=None, **kw):
        return ui.label(parent, text, kind=kind, bg=bg or ui.SURFACE, **kw)

    def _collapsible(self, parent, title, expanded=False):
        """Bloque plegable («Más opciones ▾»). Devuelve el marco donde ir poniendo los controles."""
        head = ui.Button(parent, "", None, style="plain", padx=0, pady=4)
        body = tk.Frame(parent, bg=ui.SURFACE)
        state = {"open": expanded}

        def refresh():
            head.configure(text=("▾  " if state["open"] else "▸  ") + title)
            if state["open"]:
                body.pack(fill="x", after=head)
            else:
                body.pack_forget()

        def toggle():
            state["open"] = not state["open"]
            refresh()
        head.configure(command=toggle)
        head.pack(anchor="w", pady=(10, 0))
        refresh()
        return body

    def _card(self, parent, title=None, info=None, **kw):
        card = ui.Card(parent, **kw)
        if title:
            head = tk.Frame(card.body, bg=ui.SURFACE)
            head.pack(fill="x", pady=(0, 6))
            self._lbl(head, title, "title").pack(side="left")
            if info:
                shown = {"on": False}
                note = self._lbl(card.body, info, "muted", wraplength=560)
                btn = ui.Button(head, "i", None, style="ghost", padx=9, pady=2, radius=10)

                def toggle():
                    shown["on"] = not shown["on"]
                    if shown["on"]:
                        note.pack(fill="x", pady=(0, 8), after=head)
                    else:
                        note.pack_forget()
                btn.configure(command=toggle)
                btn.pack(side="right")
                card.body.bind("<Configure>", lambda e: note.configure(wraplength=max(200, e.width - 8)), add="+")
        return card

    # ------------------------------------------------------------------ pestañas
    def _on_tab(self, key):
        self._show_tab(key)

    def _show_tab(self, key):
        self.tab = key
        for k, page in self.pages.items():
            page.pack_forget()
        if key not in self.pages:
            sf = ui.ScrollFrame(self.pages_host)
            self.pages[key] = sf
            getattr(self, "_build_" + key)(sf.inner)
            self.built.add(key)
            if key == "panel":                  # la página se construye después de que llegó el estado
                self._paint_live(self.estado_shown)
        self.pages[key].pack(fill="both", expand=True)
        self._render_all()

    def _render_help(self):
        page = getattr(self, "help_page", None)
        if page is not None:
            page.render_for_you()

    def _render_all(self):
        for name in ("_render_calendar", "_render_hist", "_render_rewards", "_render_music_status",
                     "_render_stats", "_render_tasks_line", "_render_help"):
            fn = getattr(self, name, None)
            if fn:
                fn()

    # ------------------------------------------------------------------ TAREAS / ESTADÍSTICAS
    def _build_tareas(self, parent):
        import tasks_gui
        self.tasks_page = tasks_gui.TasksPage(self, parent)

    def _build_stats(self, parent):
        import stats_gui
        self.stats_page = stats_gui.StatsPage(self, parent)

    def _build_ayuda(self, parent):
        import help_gui
        self.help_page = help_gui.HelpPage(self, parent)

    def _build_acerca(self, parent):
        import about_gui
        self.about_page = about_gui.AboutPage(self, parent)

    def show_tutorial(self):
        if self._alive():
            import tutorial
            tutorial.show(self)

    def celebrate(self):
        import confetti
        confetti.celebrate(self.top, t("confetiTitulo"), t("confetiSub"))

    def _celebrate_with_trophy(self):
        """Confeti + el trofeo de la sesión (la pieza ganada y los logros desbloqueados), si los hubo."""
        import confetti
        buf, self._won_buf, self._cele_wait = self._won_buf, [], None
        trophy = None
        if buf:
            pieces = [w for w in buf if w.get("piece")]
            trophy = {"piece": pieces[-1]["piece"] if pieces else None,
                      "count": sum(w.get("count", 0) for w in buf),
                      "caption": buf[-1].get("caption", ""),
                      "ach_caption": [c for w in buf for c in w.get("ach_caption", [])][:3]}
        confetti.celebrate(self.top, t("confetiTitulo"), t("confetiSub"), trophy)

    def tasks_changed(self):
        self._render_tasks_line()
        self._refresh_pending_options()
        with self.lock:
            self.state["trophy_dirty"] = True
        self._render_trophy_strip()

    def _render_stats(self):
        page = getattr(self, "stats_page", None)
        if page and self.tab == "stats":
            page.refresh()

    def _render_tasks_line(self):
        lbl = getattr(self, "tasks_lbl", None)
        if lbl is None:
            return
        import tasks
        data = tasks.load()
        if tasks.roll(data):               # primer vistazo del día: crea las automáticas y arrastra pendientes
            tasks.save(data)
        done, total = tasks.progress(data)
        lbl.configure(text=t("tareasProgreso", a=done, b=total) if total else t("tareasVacio"))

    # ------------------------------------------------------------------ PANEL
    def _build_panel(self, parent):
        parent.columnconfigure(1, weight=1)
        # --- frase motivacional: arriba, a todo lo ancho y en grande ---
        phrase = ui.Card(parent, fill=ui.GHOST_BG, border=ui.GHOST_BG, pad=18, radius=16)
        phrase.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        self.phrase_lbl = tk.Label(phrase.body, text="", bg=ui.GHOST_BG, fg=ui.ACCENT, wraplength=900,
                                   justify="center", anchor="center", font=ui.F("quote"))
        self.phrase_lbl.pack(fill="x")
        phrase.body.bind("<Configure>", lambda e: self.phrase_lbl.configure(wraplength=max(300, e.width - 10)),
                         add="+")
        left = tk.Frame(parent, bg=ui.CANVAS)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        right = tk.Frame(parent, bg=ui.CANVAS)
        right.grid(row=1, column=1, sticky="nsew")

        # --- aviso visible cuando la radio no puede sonar por falta de internet (oculto por defecto) ---
        self.offline_banner = tk.Frame(left, bg=ui.DANGER_BG, highlightthickness=2, highlightbackground=ui.DANGER)
        ob = tk.Frame(self.offline_banner, bg=ui.DANGER_BG)
        ob.pack(fill="x", padx=16, pady=14)
        tk.Label(ob, text="📡", bg=ui.DANGER_BG, font=("TkDefaultFont", 26)).pack(side="left", padx=(0, 14))
        ob_txt = tk.Frame(ob, bg=ui.DANGER_BG)
        ob_txt.pack(side="left", fill="x", expand=True)
        tk.Label(ob_txt, text=t("musicaOfflineTitulo"), bg=ui.DANGER_BG, fg=ui.DANGER, font=ui.F("h2"),
                 anchor="w").pack(fill="x")
        self.offline_body = tk.Label(ob_txt, text="", bg=ui.DANGER_BG, fg=ui.INK, font=ui.F("body"), anchor="w",
                                     justify="left", wraplength=380)
        self.offline_body.pack(fill="x", pady=(2, 8))
        obb = tk.Frame(ob_txt, bg=ui.DANGER_BG)
        obb.pack(fill="x")
        ui.Button(obb, t("musicaOfflineRuido"), self._offline_use_noise, style="danger", padx=12, pady=6).pack(side="left")
        ui.Button(obb, t("musicaOfflineReintentar"), self._offline_retry, style="ghost", padx=12, pady=6).pack(side="left", padx=8)
        self._offline_shown = False

        # --- reloj en vivo: tarjeta del tema con anillo de progreso y acento del modo ---
        card = ui.Card(left, pad=18, radius=18)
        card.pack(fill="x", pady=(0, 14))
        self.live["card"] = card
        b = card.body
        self._run_key, self._run_total, self._live_estado = None, 1, None
        ring = tk.Canvas(b, height=304, bg=ui.SURFACE, highlightthickness=0, bd=0)
        ring.pack(fill="x")
        ring.bind("<Configure>", lambda e: self._paint_live(self._live_estado))
        ring.bind("<Button-1>", self._ring_click)
        self.live["ring"] = ring
        seg = ui.Segmented(b, [("T", t("colorTemporizador")), ("C", t("colorCronometro")), ("P", t("colorPomodoro"))],
                           "T", self._set_mode, padx=9, pady=6)
        seg.pack(pady=(8, 12))
        self.live["seg"] = seg
        self.live["control"] = ui.Button(b, t("btnIniciar"), self._toggle, style="primary", pady=11)
        self.live["control"].pack(fill="x")
        row2 = tk.Frame(b, bg=ui.SURFACE)
        row2.pack(fill="x", pady=(8, 0))
        self.live["row2"] = row2
        self.live["quick"] = ui.Button(row2, "5 MIN", self._quick, style="ghost", padx=6, pady=8)
        self.live["quick"].pack(side="left", expand=True, fill="x")
        self.live["extend"] = ui.Button(row2, "+5 MIN", self._extend, style="ghost", padx=6, pady=8)
        self.live["extend"].pack(side="left", expand=True, fill="x")
        # Etiqueta o tarea de las próximas sesiones: se elige antes de empezar, no después.
        trow = tk.Frame(b, bg=ui.SURFACE)
        trow.pack(fill="x", pady=(10, 0))
        self._lbl(trow, "🏷 " + t("etiquetaProxima"), "muted").pack(fill="x", anchor="w")      # texto arriba, selector debajo a todo el ancho
        self.pending_var = tk.StringVar(value=self.cfg.get("next_activity") or t("sinActividad"))
        self.pending_cb = ui.combobox(trow, self.pending_var, [])
        self.pending_cb.pack(fill="x", pady=(4, 0))
        self.pending_cb.bind("<<ComboboxSelected>>", lambda e: self._set_pending())
        self._refresh_pending_options()

        # --- calendario ---
        cal = self._card(right, t("calendarioTitulo"), info=t("calendarioAviso"), expand=False)
        cal.pack(fill="x")
        nav = tk.Frame(cal.body, bg=ui.SURFACE)
        nav.pack(fill="x", pady=(4, 6))
        ui.Button(nav, t("anterior"), lambda: self._shift_month(-1), style="ghost", pady=6).pack(side="left")
        ui.Button(nav, "📅 " + t("agendaBtn"), self._open_agenda, style="primary", pady=6).pack(side="right",
                                                                                          padx=(0, 8))
        self.month_lbl = self._lbl(nav, "", "title")
        self.month_lbl.configure(anchor="center")
        self.month_lbl.pack(side="left", expand=True, fill="x")
        ui.Button(nav, t("siguiente"), lambda: self._shift_month(1), style="ghost", pady=6).pack(side="right")
        self.cal_canvas = tk.Canvas(cal.body, bg=ui.SURFACE, highlightthickness=0, bd=0, height=300)
        self.cal_canvas.pack(fill="x")
        self.cal_canvas.bind("<Configure>", lambda e: self._render_calendar())
        self.cal_canvas.bind("<Motion>", self._cal_hover)
        self.cal_canvas.bind("<Leave>", lambda e: self.cal_tip.configure(text=""))
        self.cal_tip = self._lbl(cal.body, "", "muted")
        self.cal_tip.pack(fill="x", pady=(4, 0))
        self.legend = tk.Frame(cal.body, bg=ui.SURFACE)
        self.legend.pack(fill="x", pady=(6, 0))
        self._cal_cells = []
        # --- racha y semana ---
        stat = ui.Card(right, pad=14)
        stat.pack(fill="x", pady=(14, 0))
        self.streak_lbl = self._lbl(stat.body, "", "body", wraplength=330)
        self.streak_lbl.configure(justify="center", anchor="center", fg=ui.ACCENT)
        self.streak_lbl.pack(fill="x")
        self.week_lbl = self._lbl(stat.body, "", "body", wraplength=330)
        self.week_lbl.configure(justify="center", anchor="center", fg=ui.ACCENT)
        self.week_lbl.pack(fill="x", pady=(8, 0))
        self.tasks_lbl = self._lbl(stat.body, "", "body", wraplength=330)
        self.tasks_lbl.configure(justify="center", anchor="center", fg=ui.ACCENT)
        self.tasks_lbl.pack(fill="x", pady=(8, 0))
        self.goal_box = tk.Frame(stat.body, bg=ui.SURFACE)
        self.goal_box.pack(fill="x", pady=(10, 0))
        # --- trofeos: últimas piezas y próximo logro (toca para abrir Logros) ---
        tro = ui.Card(right, pad=14)
        tro.pack(fill="x", pady=(14, 0))
        self.trophy_strip = tk.Frame(tro.body, bg=ui.SURFACE, cursor="hand2")
        self.trophy_strip.pack(fill="x")
        self._trophy_card = tro

        if self.cfg.get("connection_mode") != "local":      # en modo app el descanso se edita en el propio reloj
            self._build_durations(left)
        self._paint_live(self.estado_shown)
        self._render_trophy_strip()

    def _enter_esc(self, widget, ok, cancel):
        """Enter confirma el cambio y Esc lo cancela (vuelve al valor guardado) en un campo de tiempo."""
        def accept(_e=None):
            ok()
            return "break"

        def revert(_e=None):
            cancel()
            try:
                widget.winfo_toplevel().focus_set()          # saca el foco del campo para que se vea cancelado
            except tk.TclError:
                pass
            return "break"
        for seq in ("<Return>", "<KP_Enter>"):
            widget.bind(seq, accept)
        widget.bind("<Escape>", revert)

    # ---- duraciones (dispositivo o modo local)
    def _build_durations(self, parent):
        local = self.cfg.get("connection_mode") == "local"
        # En modo app el Temporizador y el trabajo del Pomodoro se cambian tocando el número del reloj
        card = self._card(parent, t("subDescansoPom") if local else t("subDuraciones"))
        card.pack(fill="x", pady=(14, 0))
        self.dur_vars = {}
        row = tk.Frame(card.body, bg=ui.SURFACE)
        row.pack(fill="x", pady=(2, 0))
        fields = (("pomDescanso", "durDescanso"),) if local else (
            ("minutos", "durTemporizador"), ("pomTrabajo", "durPomodoro"), ("pomDescanso", "durDescanso"))
        for i, (key, label_key) in enumerate(fields):
            col = tk.Frame(row, bg=ui.SURFACE)
            col.pack(side="left", padx=(0, 12))
            self._lbl(col, t(label_key), "muted").pack(anchor="w")
            var = tk.StringVar(value="")
            self.dur_vars[key] = var
            sb = ui.spinbox(col, var, 1, 99, width=4)
            sb.pack(anchor="w", pady=(3, 0))
            self._enter_esc(sb, self._save_durations, self._load_durations)
        ui.Button(row, t("aplicar"), self._save_durations, style="ghost", pady=7).pack(side="right", anchor="s")
        self.dur_notice = ui.Notice(card.body, "success")
        self.dur_notice.pack(fill="x", pady=(8, 0))
        self._load_durations()

    def _load_durations(self):
        url = esp_client.url_of(self.cfg)

        def done(ok, cfg):
            if not (ok and cfg) or not self._alive() or not hasattr(self, "dur_vars"):
                return
            for key, var in self.dur_vars.items():
                if key in cfg:
                    var.set(str(cfg[key]))
        run_async(self.top, lambda: esp_client.get_device_config(url), done)

    def _save_durations(self):
        values = {k: v.get() for k, v in self.dur_vars.items() if str(v.get()).strip()}
        url = esp_client.url_of(self.cfg)

        def done(ok, res):
            if ok and res:
                self.dur_notice.set(t("durAplicadas"), "success")
                if hasattr(self, "dev_vars"):
                    self._load_device()
            else:
                self.dur_notice.set(t("errorEsp"), "error")
        run_async(self.top, lambda: esp_client.save_device_config(url, values), done)

    def _shift_month(self, d):
        y, m = self.month.year, self.month.month + d
        if m < 1:
            y, m = y - 1, 12
        if m > 12:
            y, m = y + 1, 1
        self.month = date(y, m, 1)
        self._render_calendar()

    def _render_calendar(self):
        if "panel" not in self.built:
            return
        c = self.cal_canvas
        w = max(c.winfo_width(), 300)
        c.delete("all")
        colors = {c: self._mc(c) for c in "TCP"}
        counts = stats.calendar_counts(self.log)
        self.month_lbl.configure(text=i18n.month_label(self.month.year, self.month.month))
        weeks = stats.month_grid(self.month.year, self.month.month)
        cw, ch, top = w / 7, 44, 22
        for i, name in enumerate(i18n.get("diasSemana")):
            c.create_text(cw * i + cw / 2, 8, text=name, fill=ui.MUTED, font=ui.F("tiny"))
        self._cal_cells = []
        today = date.today()
        for r, week in enumerate(weeks):
            for ci, day in enumerate(week):
                if not day:
                    continue
                x1, y1 = cw * ci + 3, top + r * ch + 2
                x2, y2 = cw * (ci + 1) - 3, top + (r + 1) * ch - 2
                d = date(self.month.year, self.month.month, day)
                outline = ui.INK if d == today else ui.SURFACE
                ui.round_rect(c, x1, y1, x2, y2, 9, fill=ui.CANVAS, outline=outline, width=2 if d == today else 1)
                c.create_text((x1 + x2) / 2, y1 + 14, text=str(day), fill=ui.INK,
                              font=ui.F("small_bold") if d == today else ui.F("small"))
                info = counts.get(d)
                if info:
                    cats = [k for k in ("T", "C", "P") if info.get(k)]
                    total = len(cats) * 9 - 4
                    px = (x1 + x2) / 2 - total / 2
                    for k in cats:
                        c.create_oval(px, y2 - 12, px + 5, y2 - 7, fill=colors[k], outline="")
                        px += 9
                    names = []
                    for k in cats:
                        names.append(f"{mode_name('W' if k == 'P' else k)}: {info[k]}")
                    self._cal_cells.append((x1, y1, x2, y2, f"{d.day}/{d.month}  ·  " + ", ".join(names)))
        c.configure(height=top + max(len(weeks), 4) * ch + 4)
        for child in self.legend.winfo_children():
            child.destroy()
        for k, key in (("T", "colorTemporizador"), ("C", "colorCronometro"), ("P", "colorPomodoro")):
            item = tk.Frame(self.legend, bg=ui.SURFACE)
            item.pack(side="left", padx=(0, 14))
            dot = tk.Canvas(item, width=10, height=10, bg=ui.SURFACE, highlightthickness=0)
            dot.create_oval(1, 1, 9, 9, fill=colors[k], outline="")
            dot.pack(side="left", padx=(0, 5))
            self._lbl(item, t(key), "muted").pack(side="left")
        # racha / semana / frase
        n = stats.streak(stats.calendar_counts([s for s in self.log if s.get("modo") != "D"]), None, stats.streak_days(self.cfg))   # igual que Logros
        name = self.cfg.get("user_name", "").strip()
        prefix = t("rachaPrefijoConNombre", n=name) if name else t("rachaPrefijo")
        self.streak_lbl.configure(text=f"{prefix}{n}{t('rachaSufijo')}")
        s, m = stats.week_summary(self.log)
        self.week_lbl.configure(text=t("resumenSemanaTexto", s=s, m=m))
        self._render_goals()
        self.phrase_lbl.configure(text=stats.phrase_of_day(i18n.get("frasesPorDefecto"), self.cfg.get("phrases", [])))

    def _render_goals(self):
        box = getattr(self, "goal_box", None)
        if box is None:
            return
        for w in box.winfo_children():
            w.destroy()
        for key, done, goal in stats.goal_progress(self.log, self.cfg):
            frac = min(1.0, done / goal)
            text = t("metaHoy" if key == "day" else "metaSemana", a=done, b=goal)
            if done >= goal:
                text += "  " + t("metaCumplida")
            lab = self._lbl(box, text, "body", wraplength=330)
            lab.configure(fg=ui.SUCCESS if done >= goal else ui.ACCENT, anchor="center", justify="center")
            lab.pack(fill="x")
            bar = tk.Canvas(box, height=10, bg=ui.SURFACE, highlightthickness=0, bd=0)
            bar.pack(fill="x", pady=(3, 8))

            def paint(e=None, c=bar, f=frac, ok=done >= goal):
                w = max(c.winfo_width(), 40)
                c.delete("all")
                ui.round_rect(c, 0, 0, w, 10, 5, fill=ui.TAG_BG, outline="")
                if f > 0:
                    ui.round_rect(c, 0, 0, max(10, w * f), 10, 5, fill=ui.SUCCESS if ok else ui.PRIMARY, outline="")
            bar.bind("<Configure>", paint)

    def _cal_hover(self, e):
        for x1, y1, x2, y2, text in self._cal_cells:
            if x1 <= e.x <= x2 and y1 <= e.y <= y2:
                self.cal_tip.configure(text=text)
                return
        self.cal_tip.configure(text="")

    # ---- editar el tiempo tocando el número (modo "Solo en la app")
    def _time_editable(self, estado):
        return bool(estado and self.cfg.get("connection_mode") == "local" and not estado.get("ejecutando")
                    and estado.get("modo") in ("T", "P"))

    def _ring_click(self, e):
        ring = self.live["ring"]
        est = self._live_estado
        if not self._time_editable(est):
            return
        mid = ring.winfo_width() / 2
        if abs(e.x - mid) < 100 and abs(e.y - 144) < 46:
            self._edit_time()
        elif est.get("modo") == "P" and abs(e.x - mid) < 90 and 276 <= e.y <= 302:
            self._edit_time("pomDescanso")

    def _edit_time(self, key=None):
        if getattr(self, "_time_editor", None) is not None:
            return
        import local_timer
        est = self._live_estado
        key = key or ("minutos" if est.get("modo") == "T" else "pomTrabajo")
        self._edit_key = key
        ring = self.live["ring"]
        color = ui.SUCCESS if (est.get("fase") == "D" or key == "pomDescanso") else self._mc("T" if est.get("modo") == "T" else "P")
        box = tk.Frame(ring, bg=ui.SURFACE)                       # editor sin marco: mismo estilo que el reloj
        ed = tk.Entry(box, font=ui.F("clock"), width=2, justify="center", bg=ui.SURFACE, fg=ui.INK,
                      insertbackground=color, insertwidth=3, relief="flat", bd=0, highlightthickness=0,
                      selectbackground=ui.mix(ui.SURFACE, color, 0.30), selectforeground=ui.INK)
        ed.insert(0, str(local_timer.durations()[key]))
        ed.pack(side="left")
        tk.Label(box, text="min", bg=ui.SURFACE, fg=ui.MUTED, font=ui.F("body")).pack(side="left", anchor="s",
                                                                                     pady=(0, 12), padx=(2, 0))
        line = tk.Frame(ring, bg=color, height=3, width=96)
        box.place(x=ring.winfo_width() / 2, y=140, anchor="center")
        line.place(x=ring.winfo_width() / 2 - 22, y=176, anchor="center")
        ed.select_range(0, "end")
        ed.focus_force()                                         # sin esto, en algunos escritorios Linux Enter/Esc no llegan
        self._time_line = line
        self._time_editor = box
        self._time_entry = ed
        for seq in ("<Return>", "<KP_Enter>"):
            ed.bind(seq, lambda e, k=key: (self._commit_time(k), "break")[1])
        ed.bind("<Escape>", lambda e: (self._cancel_time_edit(), "break")[1])
        ed.bind("<FocusOut>", lambda e: self._commit_time(key))
        ed.bind("<Key>", lambda e: self.top.after_idle(self._limit_time_entry))
        self._paint_live(est)                                    # quita el número fijo y muestra la ayuda

    def _cancel_time_edit(self):
        """Esc: cierra el editor sin guardar (se anula el «commit» por pérdida de foco)."""
        self._time_entry = None
        self._close_time_editor()

    def _limit_time_entry(self):
        ed = getattr(self, "_time_entry", None)
        if ed is not None:
            try:
                clean = "".join(ch for ch in ed.get() if ch.isdigit())[:2]     # solo hasta 2 dígitos
                if clean != ed.get():
                    ed.delete(0, "end")
                    ed.insert(0, clean)
            except tk.TclError:
                pass

    def _close_time_editor(self):
        self._edit_key = None
        box, self._time_editor = getattr(self, "_time_editor", None), None
        line, self._time_line = getattr(self, "_time_line", None), None
        self._time_entry = None
        for w in (box, line):
            if w is not None:
                try:
                    w.destroy()
                except tk.TclError:
                    pass
        if self.live.get("ring") is not None and self._live_estado:
            self._paint_live(self._live_estado)

    def _commit_time(self, key):
        ed = getattr(self, "_time_entry", None)
        if ed is None or getattr(self, "_time_editor", None) is None:
            return
        raw = ed.get().strip().split(":")[0]
        self._close_time_editor()
        try:
            minutes = max(1, min(99, int(raw)))
        except ValueError:
            return                                              # texto inválido: se deja el tiempo anterior
        esp_client.save_device_config(esp_client.url_of(self.cfg), {key: minutes})
        if hasattr(self, "dur_vars"):
            self._load_durations()
        est = self._live_estado
        if est:                                                 # refleja el cambio sin esperar al siguiente ciclo
            self._paint_live(est if key == "pomDescanso" else dict(est, segundos=minutes * 60))

    # ---- reloj en vivo
    def _paint_live(self, estado):
        if "panel" not in self.built:
            return
        L = self.live
        self._live_estado = estado
        self._sync_strict_lock()
        cat = "T"
        phase_break = False
        if estado:
            cat = "T" if estado.get("modo") == "T" else "C" if estado.get("modo") == "C" else "P"
            phase_break = estado.get("modo") == "P" and estado.get("fase") == "D"
        color = ui.SUCCESS if phase_break else self._mc(cat)
        running = bool(estado and estado.get("ejecutando"))
        secs = int((estado or {}).get("segundos") or 0)
        # progreso: cuenta regresiva respecto del tiempo con que arrancó la fase; cronómetro: vuelta de 60 s
        if estado and cat != "C":
            key = (estado.get("idArranque"), estado.get("modo"), estado.get("fase"), running)
            if key != self._run_key:
                self._run_key, self._run_total = key, max(secs, 1)
            self._run_total = max(self._run_total, secs, 1)
            frac = secs / self._run_total
        elif estado:
            frac = (secs % 60) / 60.0 if running else 0.0
        else:
            frac = 0.0

        c = L["ring"]
        w = max(c.winfo_width(), 200)
        c.delete("all")
        cx, cy, r, tw = w / 2, 148, 102, 9
        editing_break = getattr(self, "_edit_key", None) == "pomDescanso" and getattr(self, "_time_editor", None) is not None
        name = (mode_name("D") if (phase_break or editing_break) else
                mode_name("W" if estado and estado.get("modo") == "P" else (estado or {}).get("modo", "T"))) \
            if estado else t("tipoTemporizador")
        f = ui.F("bold")
        tw_txt = ui.tkfont.Font(font=f).measure(name)
        c.create_oval(cx - tw_txt / 2 - 18, 17, cx - tw_txt / 2 - 8, 27, fill=color, outline="")
        c.create_text(cx + 4, 22, text=name, font=f, fill=ui.INK)
        box = (cx - r, cy - r, cx + r, cy + r)
        track = ui.mix(ui.SURFACE, ui.INK, .09)
        if not estado:
            arc_col, frac_draw = track, 0
        elif running:
            arc_col, frac_draw = color, frac
        else:
            arc_col, frac_draw = ui.mix(ui.SURFACE, color, .4), (frac if cat != "C" else 1.0)
        ring_photo = ring_img.photo(r, tw, track, arc_col, frac_draw)       # anillo suavizado (antialiasing)
        if ring_photo is not None:
            self._ring_photo = ring_photo                                    # Tkinter no guarda la referencia
            c.create_image(cx, cy, image=ring_photo)
        else:                                                                # sin Pillow: dibujo básico de Tkinter
            c.create_oval(*box, outline=track, width=tw)
            if frac_draw >= 0.999:
                c.create_oval(*box, outline=arc_col, width=tw)
            elif frac_draw > 0.002:
                c.create_arc(*box, start=90, extent=-360 * frac_draw, style="arc", outline=arc_col, width=tw)
                ang = math.radians(90 - 360 * frac_draw)                     # tapa redondeada en el extremo
                for a_ in (math.radians(90), ang):
                    ex, ey = cx + r * math.cos(a_), cy - r * math.sin(a_)
                    c.create_oval(ex - tw / 2, ey - tw / 2, ex + tw / 2, ey + tw / 2, fill=arc_col, outline="")
        editing = getattr(self, "_time_editor", None) is not None
        if not editing:                                            # mientras se edita, el campo ocupa su lugar
            c.create_text(cx, cy - 4, text=stats.fmt_clock(secs) if estado else "--:--", font=ui.F("clock"),
                          fill=ui.INK if estado else ui.MUTED)
        status = (t("estEjecucion") if running else t("estEspera")) if estado else t("sinConexion")
        sf = ui.F("small_bold")
        sw = ui.tkfont.Font(font=sf).measure(status) + 30
        pill = ui.mix(ui.SURFACE, color, .14) if running else ui.TAG_BG
        ui.round_rect(c, cx - sw / 2, cy + 36, cx + sw / 2, cy + 58, 11, fill=pill, outline="")
        c.create_oval(cx - sw / 2 + 10, cy + 43, cx - sw / 2 + 18, cy + 51, fill=color if running else ui.DOT_OFF, outline="")
        c.create_text(cx + 6, cy + 47, text=status, font=sf, fill=ui._readable(color, pill) if running else ui.MUTED)
        editable = self._time_editable(estado)
        c.configure(cursor="xterm" if editable else "")
        if editable:                                            # modo app y en espera: el número se puede tocar
            c.create_text(cx, 262, text="Enter ✓   ·   Esc ✕" if editing else "✎ " + t("editarHint"),
                          font=ui.F("small"), fill=ui.MUTED)
        elif getattr(self, "_time_editor", None) is not None:
            self._close_time_editor()
        if self.cfg.get("connection_mode") == "local" and estado and estado.get("modo") == "P":
            self._paint_break_chip(c, cx, estado, editable, editing_break)

        # Solo se toca un widget cuando su estado cambia: volver a empaquetar o repintar botones cada
        # segundo les quita el "hover" y hace que parpadeen (y puede perder clics).
        if L.get("_color") != color:
            L["_color"] = color
            L["seg"].set_accent(color)
            L["control"].set_accent(color)
            for k in ("quick", "extend"):
                L[k].set_accent(color)
        if estado and L["seg"].value != cat:
            L["seg"].set(cat)
        label = t("btnDetener") if running else t("btnIniciar")
        if L.get("_label") != label:
            L["_label"] = label
            L["control"].configure(text=label)
        if estado and running:
            layout = "extend" if estado.get("modo") != "C" else "none"
        else:
            layout = "quick"
        if L.get("_layout") != layout:
            L["_layout"] = layout
            L["quick"].pack_forget()
            L["extend"].pack_forget()
            if layout != "none":
                L[layout].pack(side="left", expand=True, fill="x")

    def _paint_break_chip(self, c, cx, estado, editable, active):
        """Pomodoro en modo app: el descanso se muestra (y se edita) en el propio reloj, como el tiempo de trabajo."""
        import local_timer
        d = local_timer.durations()
        txt = "☕ " + t("relojDescanso", n=d["pomDescanso"]) + ("  ✎" if editable else "")
        f = ui.F("small_bold")
        w = ui.tkfont.Font(font=f).measure(txt) + 28
        fill = ui.mix(ui.SURFACE, ui.SUCCESS, .22 if active else .12) if editable else ui.TAG_BG
        ui.round_rect(c, cx - w / 2, 278, cx + w / 2, 300, 11, fill=fill, outline="")
        c.create_text(cx, 289, text=txt, font=f, fill=ui._readable(ui.SUCCESS, fill) if editable else ui.MUTED)

    def _mc(self, code):
        return ui.mode_color(code, self.cfg.get("mode_colors"))

    def _cmd(self, func, after=None):
        url = esp_client.url_of(self.cfg)
        run_async(self.top, lambda: func(url), lambda ok, res: (after(ok, res) if after else None))

    def _confirm_early_stop(self):
        """True si se puede seguir: no hay sesión que perder o el usuario confirmó terminarla antes de tiempo.
        En modo estricto hay que confirmar `strict_confirms` veces seguidas; cerrar o cancelar en cualquier paso la mantiene."""
        est = getattr(self, "_live_estado", None)
        times = guard.confirmations_needed(self.cfg, est)
        if not times:
            return True
        import mascot
        mascot.set_wary(True)                                   # Brote te mira raro mientras dudas
        try:
            return self._confirm_early_stop_steps(est, times)
        finally:
            mascot.set_wary(False)

    def _confirm_early_stop_steps(self, est, times):
        strict = bool(self.cfg.get("strict_mode"))
        total = max(getattr(self, "_run_total", 0), int(est.get("segundos") or 0))
        done = max(0, total - int(est.get("segundos") or 0))
        body = t("stopCuerpo", a=stats.fmt_long(done), b=stats.fmt_long(total))
        for step in range(1, times + 1):
            text = body + ("\n\n" + t("estrictoPaso", a=step, b=times) if strict else "")
            stop, never = ui.confirm_stop(
                self.top, t("stopTitulo"), text, random.choice(i18n.get("motivaStop")),
                t("stopSeguir"), t("stopTerminar"), None if strict else t("stopNoPreguntar"))
            if not stop:
                return False
            if never and not strict:
                self._save_cfg(confirm_stop=False)
        if strict and self.cfg.get("strict_stop_code"):         # última barrera: escribir un código aleatorio
            if not ui.ask_code(self.top, t("stopCodigoTitulo"), t("stopCodigoTexto"), guard.new_code(),
                               t("stopTerminar"), t("stopSeguir"), t("estrictoCodigoMal")):
                return False
        # si mientras se confirmaba la sesión terminó sola, no hay nada que detener (y un «toggle» la reiniciaría)
        return guard.session_at_risk(getattr(self, "_live_estado", None))

    def _apply_estado(self, estado):
        """Muestra de inmediato un estado nuevo sin esperar al siguiente ciclo de consulta."""
        if not estado or not self._alive():
            return
        with self.lock:
            self.state["estado"] = estado
            self.state["fast_until"] = time.time() + 3
        self._sync_strict_lock()
        self.estado_shown = estado
        self._paint_live(estado)

    def _set_mode(self, code):
        est = getattr(self, "_live_estado", None)
        if est and est.get("modo") == code:
            return
        if not self._confirm_early_stop():                    # cambiar de modo con una sesión en curso la termina
            if est and "seg" in self.live:
                self.live["seg"].set(est.get("modo"))
            return
        url = esp_client.url_of(self.cfg)
        if url == esp_client.LOCAL:                           # el motor local responde al instante: sin hilos
            self._apply_estado(esp_client.set_mode(url, code))
            return
        if est:                                               # dispositivo: se refleja ya y se confirma después
            self._paint_live(dict(est, modo=code, ejecutando=False))
        run_async(self.top, lambda: esp_client.set_mode(url, code),
                  lambda ok, res: self._apply_estado(res) if ok else None)

    def _pending_activity(self):
        """Etiqueta elegida para las próximas sesiones ("" = ninguna)."""
        v = (self.cfg.get("next_activity") or "").strip()
        return v

    def _refresh_pending_options(self):
        """Opciones del selector: sin etiqueta, tus etiquetas y las tareas pendientes de hoy."""
        cb = getattr(self, "pending_cb", None)
        if cb is None:
            return
        import tasks
        opts = [t("sinActividad")]
        for name in self.cfg.get("tags", []):
            if name and name not in opts:
                opts.append(name)
        try:
            for it in tasks.today_items(tasks.load()):
                if not it.get("done") and it["text"] not in opts:
                    opts.append(it["text"])
        except Exception:
            pass
        cur = self._pending_activity()
        if cur and cur not in opts:                  # la etiqueta elegida ya no existe: se vuelve a «sin etiqueta»
            cur = ""
            self.cfg["next_activity"] = ""
            self._save_cfg(next_activity="")
        try:
            cb.configure(values=opts)
            self.pending_var.set(cur or t("sinActividad"))
        except tk.TclError:
            pass

    def _set_pending(self):
        v = self.pending_var.get()
        self._save_cfg(next_activity="" if v == t("sinActividad") else v)

    def _toggle(self):
        if not self._confirm_early_stop():
            return
        est = getattr(self, "_live_estado", None) or {}
        starting = not est.get("ejecutando")
        act = self._pending_activity() if starting else ""
        url = esp_client.url_of(self.cfg)
        if starting and act and url != esp_client.LOCAL and est.get("modo") == "T":       # dispositivo: la etiqueta viaja con el inicio rápido
            mins = max(1, min(99, int(est.get("segundos") or 0) // 60 or 25))
            run_async(self.top, lambda: esp_client.start_session(url, mins, act),
                      lambda ok, res: self._after_start_session(ok, True))
            return
        self._cmd(lambda u: esp_client.toggle_run(u, act), self._after_start_session if starting else None)

    def _autostart_on(self):
        try:
            from autostart import install_autostart
            return install_autostart.is_enabled()
        except Exception:
            return False

    def _toggle_autostart(self):
        try:
            from autostart import install_autostart
            ok = install_autostart.set_enabled(bool(self.autostart_var.get()))
        except Exception:
            ok = False
        if not ok:                                             # no se pudo: el interruptor vuelve a su estado real
            self.autostart_var.set(self._autostart_on())
            self.autostart_notice.set(t("inicioSistemaError"), "error")
        else:
            self.autostart_notice.set("", "error")

    def _session_running(self):
        est = getattr(self, "_live_estado", None)
        return bool(est and est.get("ejecutando"))

    def _toggle_bridge(self):
        """Apagar la conexión con la extensión en plena sesión soltaría el bloqueo web: no se permite."""
        if self._session_running():
            self.bridge_var.set(bool(self.cfg.get("bridge", True)))
            self.port_notice.set(t("puenteBloqueado"), "error")
            return
        self._save_cfg(bridge=bool(self.bridge_var.get()))

    def _save_port(self):
        """Cambia el puerto del puente con la extensión (1024–65535) y lo aplica al instante."""
        import bridge
        if self._session_running():
            self.port_var.set(str(self.cfg.get("bridge_port", 8765)))
            self.port_notice.set(t("puenteBloqueado"), "error")
            return
        try:
            port = int(self.port_var.get())
            if not 1024 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.port_notice.set(t("puertoInvalido"), "error")
            return
        if not bridge.set_port(port):
            self.port_var.set(str(self.cfg.get("bridge_port", 8765)))
            self.port_notice.set(t("puertoOcupado", p=port), "error")
            return
        self._save_cfg(bridge_port=port)
        self.port_notice.set(t("puertoAplicado", p=port), "success")

    def profile(self):
        """Perfil de uso (adaptive.analyze) o None si la adaptación está apagada o no hay historial."""
        import adaptive
        if not self.cfg.get("adaptive", True):
            return None
        if self.log_loaded:
            return adaptive.analyze(self.log, self.cfg)
        return adaptive.load_profile(self.cfg)

    def _fatigue_notice(self):
        """Al empezar a trabajar: si hoy ya pasaste el punto donde sueles cansarte, lo dice con el porqué."""
        import adaptive
        try:
            msg = adaptive.fatigue_notice(self.profile())
        except Exception:
            msg = None
        if msg:
            self._toast_msg(t(msg[0], **msg[1]))

    def _toast_msg(self, text):
        notify = self.state.get("notify")
        if notify:
            threading.Thread(target=notify, args=("Focus Relay", text), daemon=True).start()

    def start_task(self, text):
        """Inicia una sesión dedicada a una tarea (la etiqueta de la sesión es el texto de la tarea).

        Devuelve False si ya hay una sesión en curso.
        """
        est = getattr(self, "_live_estado", None)
        if est and est.get("ejecutando"):
            return False
        url = esp_client.url_of(self.cfg)
        minutes = 25
        try:                                                           # duración típica que esa tarea te ha llevado
            import adaptive
            prof = self.profile()
            minutes = adaptive.estimate_for(prof, esp_client.fit_activity(text)) or minutes if prof else minutes
        except Exception:
            pass
        if est and est.get("modo") == "T" and int(est.get("segundos") or 0) >= 60:
            minutes = max(1, min(99, int(est["segundos"]) // 60))      # respeta el tiempo ya elegido
        run_async(self.top, lambda: esp_client.start_current(url, minutes, text),
                  lambda ok, res: self._after_start_task(ok, res, text, minutes))
        self.tabs.set("panel")
        self._show_tab("panel")
        return True

    def _after_start_task(self, ok, res, text="", minutes=25):
        if ok and res:
            self._apply_estado(res if isinstance(res, dict) else None)
            self._fatigue_notice()
            if self.cfg.get("minimize_on_task", False):          # a trabajar: la app se esconde y avisa
                self._minimize_with_notice(t("tareaIniciada", task=text, min=minutes))

    def _minimize_with_notice(self, msg):
        notify = self.state.get("notify")
        if notify:
            threading.Thread(target=notify, args=("Focus Relay", msg), daemon=True).start()
        try:
            self.top.iconify()
        except tk.TclError:
            pass

    def _after_start_session(self, ok, res):
        """Al iniciar cualquier sesión (botón Iniciar o +5 min): si está activada la opción, minimiza y avisa."""
        if ok and res:
            self._fatigue_notice()
        if not ok or not res or not self.cfg.get("minimize_on_session", False):
            return
        url = esp_client.url_of(self.cfg)

        def with_estado(ok2, est):
            if not (ok2 and isinstance(est, dict) and est.get("ejecutando")):
                return                                           # no arrancó (o ya terminó): no se minimiza
            modo = est.get("modo")
            name = mode_name("W" if modo == "P" else modo)
            mins = int(est.get("segundos") or 0) // 60
            detail = f"{name} · {mins} min" if modo in ("T", "P") and mins else name
            self._minimize_with_notice(t("sesionIniciada", detail=detail))
        run_async(self.top, lambda: esp_client.get_estado(url), with_estado)

    def task_seconds(self, item):
        """Tiempo de enfoque ya dedicado a una tarea: sesiones con su etiqueta desde el día en que apareció."""
        label = esp_client.fit_activity(item["text"])
        try:
            since = datetime.fromisoformat(item.get("carried_from") or item["date"]).timestamp()
        except ValueError:
            since = 0
        return sum(int(s.get("duracion_seg", 0)) for s in self.log
                   if s.get("actividad") == label and s.get("modo") != "D" and (s.get("epoch") or 0) >= since)

    def _open_agenda(self):
        import agenda_gui
        agenda_gui.open_agenda(self)

    def _quick(self):
        act = self._pending_activity()
        self._cmd(lambda u: esp_client.start_session(u, 5, act), self._after_start_session)

    def _extend(self):
        self._cmd(esp_client.extend_session)

    # ------------------------------------------------------------------ bucle de estado
    def _tick(self):
        if not self._alive():
            return
        try:
            self._tick_once()
        except Exception:                 # un error de pintado no debe congelar el reloj
            import traceback
            traceback.print_exc()
        if self._alive():
            self.top.after(self._next_tick_delay(), self._tick)

    def _next_tick_delay(self):
        """Milisegundos hasta el próximo repintado. En modo app el reloj se alinea con el instante exacto en que cambia
        el segundo (antes: un temporizador de 500 ms sin fase hacía que algunos segundos duraran de más y otros de menos)."""
        est = self.estado_shown if isinstance(self.estado_shown, dict) else None
        if est and est.get("ejecutando") and est.get("proximoMs") is not None and self.cfg.get("connection_mode") == "local":
            return max(15, min(1000, int(est["proximoMs"]) + 8))
        if est and est.get("ejecutando"):
            return 300 if self.cfg.get("eco_mode") else 120    # con dispositivo: lecturas del ESP, se afina la espera
        return 600 if self.cfg.get("eco_mode") else 300

    def _tick_once(self):
        local = self.cfg.get("connection_mode") == "local"
        live = esp_client.get_estado(esp_client.LOCAL) if local else None   # modo app: lectura directa y sin retraso
        with self.lock:
            self.state["fast_until"] = time.time() + 3
            if live is not None:
                self.state["estado"] = live
            estado = self.state.get("estado")
            connected = self.state.get("connected", False)
            version = self.state.get("rewards_version", 0)
            celebrate = self.state.get("celebrate", 0)
            toasts, self.state["toasts"] = self.state.get("toasts", []), []
            won, self.state["won"] = self.state.get("won", []), []
        if toasts:
            self._show_toast("   ·   ".join(x["text"] for x in toasts[-3:]))
        now = time.time()
        self._won_buf = [w for w in self._won_buf + won if now - w["t"] < 6]      # trofeos recientes (pieza y logros)
        if celebrate != self._celebrate_seen:
            self._celebrate_seen = celebrate
            if self.cfg.get("confetti", True):
                self._cele_wait = now
        if self._cele_wait is not None and (self._won_buf or now - self._cele_wait > 2.0):
            self._celebrate_with_trophy()
        self.hero.set_status(t("pillLocal") if local else (t("pillConectado") if connected else t("pillSinConexion")),
                             True if local else connected)
        if estado != self.estado_shown:
            self.estado_shown = estado
            self._paint_live(estado)
        if getattr(self, "_rewards_version", 0) != version:
            self._rewards_version = version
            self._render_rewards()
        self._render_music_status()
        today = date.today()
        if getattr(self, "_day", today) != today:
            self._day = today
            page = getattr(self, "tasks_page", None)
            if page:
                page.refresh()
            self._render_tasks_line()
        self._day = today

    def _periodic_log(self):
        if not self._alive():
            return
        self._refresh_log()
        self.top.after(20000, self._periodic_log)

    def _device_achievements(self):
        """Con dispositivo el historial llega por red: aquí se detectan los logros nuevos."""
        import insights
        import tasks
        import trophies
        from config import save_data
        data = load_data()
        new = trophies.check_achievements(insights.totals(self.log, tasks.done_by_date(tasks.load())), data)
        save_data(data)
        if new:
            self._show_toast("🏆 " + "   ·   ".join(
                t("toastLogro", name=t("logro_" + a["family"], n=a["goal"])) for a in new[:3]))

    def _refresh_log(self):
        url = esp_client.url_of(self.cfg)

        def done(ok, res):
            if ok and res is not None:
                changed = res != self.log or not self.log_loaded
                self.log, self.log_loaded, self.log_time = res, True, datetime.now()
                if changed:                  # si nada cambió no se reconstruye (evita cerrar listas abiertas)
                    if esp_client.url_of(self.cfg) != esp_client.LOCAL:
                        self._device_achievements()
                    self._render_all()
                    page = getattr(self, "tasks_page", None)
                    if page and self.tab == "tareas":
                        page.refresh()
        run_async(self.top, lambda: esp_client.get_log(url), done)

    # ------------------------------------------------------------------ HISTORIAL
    def _build_hist(self, parent):
        stat = self._card(parent, t("estadisticasActividadTitulo"), info=t("estadisticasActividadAviso"))
        stat.pack(fill="x", pady=(0, 14))
        self.tagstat_frame = tk.Frame(stat.body, bg=ui.SURFACE)
        self.tagstat_frame.pack(fill="x")

        ses = self._card(parent, t("sesionesTitulo"), info=t("sesionesAviso"))
        ses.pack(fill="x")
        self.table_frame = tk.Frame(ses.body, bg=ui.SURFACE)
        self.table_frame.pack(fill="x", pady=(4, 0))
        self.more_btn = ui.Button(ses.body, t("mostrarMas"), self._toggle_all, style="ghost", pady=6)
        self.queried_lbl = self._lbl(ses.body, "", "muted")
        self.queried_lbl.pack(fill="x", pady=(10, 0))
        actions = tk.Frame(ses.body, bg=ui.SURFACE)
        actions.pack(fill="x", pady=(10, 0))
        ui.Button(actions, t("borrarHistorial"), self._clear_log, style="danger").pack(side="left")
        ui.Button(actions, t("descargarCSV"), self._export_csv, style="ghost").pack(side="left", padx=8)
        self.hist_notice = ui.Notice(ses.body, "success")
        self.hist_notice.pack(fill="x", pady=(10, 0))

    def _tag_options(self):
        tags = list(self.cfg.get("tags", []))
        for s in self.log:                       # etiquetas que ya usan sesiones del historial
            a = s.get("actividad")
            if a and a not in tags:
                tags.append(a)
        return tags

    def _grid_header(self, frame, names, weights):
        for i, (n, w) in enumerate(zip(names, weights)):
            frame.columnconfigure(i, weight=w)
            tk.Label(frame, text=n.upper(), bg=ui.SURFACE, fg=ui.MUTED, font=ui.F("eyebrow"),
                     anchor="w").grid(row=0, column=i, sticky="we", padx=4, pady=(0, 4))

    def _render_hist(self):
        if "hist" not in self.built:
            return
        # --- estadísticas por etiqueta ---
        fr = self.tagstat_frame
        for w in fr.winfo_children():
            w.destroy()
        rows = stats.tag_stats(self.log)
        if not rows:
            self._lbl(fr, t("sinDatosActividades"), "muted").pack(fill="x")
        else:
            self._grid_header(fr, [t("thEtiqueta"), t("thSesiones"), t("thTiempoTotal"), t("thCompletadas"),
                                   t("thIncompletas")], [3, 1, 1, 1, 1])
            for r, (name, a) in enumerate(rows, start=1):
                vals = [name or t("sinActividad"), a["sessions"], stats.fmt_long(a["seconds"]), a["done"], a["undone"]]
                for c, v in enumerate(vals):
                    tk.Label(fr, text=str(v), bg=ui.SURFACE, fg=ui.INK, font=ui.F("small"), anchor="w").grid(
                        row=r, column=c, sticky="we", padx=4, pady=3)

        # --- tabla de sesiones ---
        tf = self.table_frame
        for w in tf.winfo_children():
            w.destroy()
        if not self.log:
            self._lbl(tf, t("sinSesiones"), "muted").pack(fill="x")
            self.more_btn.pack_forget()
        else:
            self._grid_header(tf, [t("thNumero"), t("thDuracion"), t("thTipo"), t("thFecha"), t("thActividad"),
                                   t("thEstadoSesion")], [0, 1, 2, 3, 3, 1])
            order = list(range(len(self.log)))[::-1]
            visible = order if self.show_all else order[:5]
            fmt = i18n.locale_date_format()
            options = [t("sinActividad")] + self._tag_options()
            for r, i in enumerate(visible, start=1):
                s = self.log[i]
                secs = int(s.get("duracion_seg", 0))
                when = datetime.fromtimestamp(s["epoch"]).strftime(fmt) if s.get("epoch") else t("sinFechaAun")
                cells = [str(i + 1), f"{secs // 60}m {secs % 60}s", mode_name(s.get("modo")), when]
                for c, v in enumerate(cells):
                    tk.Label(tf, text=v, bg=ui.SURFACE, fg=ui.INK, font=ui.F("small"), anchor="w").grid(
                        row=r, column=c, sticky="we", padx=4, pady=3)
                if s.get("modo") == "D":
                    tk.Label(tf, text="—", bg=ui.SURFACE, fg=ui.MUTED, anchor="w").grid(row=r, column=4, sticky="we", padx=4)
                else:
                    var = tk.StringVar(value=s.get("actividad") or options[0])
                    cb = ui.combobox(tf, var, options)
                    cb.configure(width=16)
                    cb.grid(row=r, column=4, sticky="we", padx=4, pady=2)
                    cb.bind("<<ComboboxSelected>>", lambda e, idx=i, v=var: self._tag(idx, v.get()))
                done = s.get("completada")
                txt = t("estadoCompletada") if done is True else t("estadoIncompleta") if done is False else t("estadoDesconocido")
                col = ui.SUCCESS if done is True else ui.DANGER if done is False else ui.MUTED
                tk.Label(tf, text=txt, bg=ui.SURFACE, fg=col, font=ui.F("small_bold"), anchor="w").grid(
                    row=r, column=5, sticky="we", padx=4)
            if len(self.log) > 5:
                self.more_btn.configure(text=t("mostrarMenos") if self.show_all else t("mostrarMas"))
                self.more_btn.pack(pady=(10, 0), before=self.queried_lbl)
            else:
                self.more_btn.pack_forget()
        when = self.log_time.strftime(i18n.locale_date_format()) if self.log_time else ""
        self.queried_lbl.configure(text=t("consultadoEl") + when)

    def _toggle_all(self):
        self.show_all = not self.show_all
        self._render_hist()

    def _tag(self, index, value):
        activity = "" if value == t("sinActividad") else value
        if 0 <= index < len(self.log):
            self.log[index]["actividad"] = activity
        url = esp_client.url_of(self.cfg)
        entry = dict(self.log[index]) if 0 <= index < len(self.log) else {}
        run_async(self.top, lambda: esp_client.tag_entry(url, entry, activity),
                  lambda ok, res: self._after_tag(ok and res))
        self._render_hist()

    def _after_tag(self, ok):
        if not ok:
            self.hist_notice.set(t("errorEsp"), "error")
            self._refresh_log()

    def _clear_log(self):
        if not ui.confirm(self.top, t("borrarHistorialTitulo"), t("confirmBorrarHistorial"), yes=t("borrar"), danger=True):
            return
        url = esp_client.url_of(self.cfg)

        def done(ok, res):
            if ok and res:
                self.log = []
                self._render_all()
            else:
                self.hist_notice.set(t("errorEsp"), "error")
        run_async(self.top, lambda: esp_client.clear_log(url), done)

    def _export_csv(self):
        path = filedialog.asksaveasfilename(parent=self.top, defaultextension=".csv", initialfile="sessions.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        notice = getattr(self, "hist_notice", None) or getattr(self, "data_notice", None)
        text = stats.export_csv(self.log, t("csvEncabezado"), mode_name, t("sinFechaAun"), "%Y-%m-%d %H:%M:%S")
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:     # utf-8-sig: Excel lo abre bien
                f.write(text)
            notice.set(t("csvGuardado"), "success")
        except OSError as exc:
            notice.set(str(exc), "error")

    # ------------------------------------------------------------------ LOGROS Y COLECCIÓN
    def _build_premios(self, parent):
        self.achievements_host = tk.Frame(parent, bg=ui.CANVAS)
        self.achievements_host.pack(fill="x")
        rw = self._card(parent, t("premiosTitulo"), info=t("premiosAviso"))
        rw.pack(fill="x", pady=(0, 14))
        self._lbl(rw.body, t("temasPiezas"), "bold").pack(fill="x")
        cats = tk.Frame(rw.body, bg=ui.SURFACE)
        cats.pack(fill="x", pady=(4, 8))
        self.cat_vars = {}
        selected = set(self.cfg.get("reward_categories", []))
        for i, c in enumerate(rewards.CATEGORY_ORDER):
            v = tk.BooleanVar(value=c in selected)
            self.cat_vars[c] = v
            ui.checkbutton(cats, t("cat_" + c), v, command=self._save_cats).grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 18))
        head = tk.Frame(rw.body, bg=ui.SURFACE)
        head.pack(fill="x", pady=(4, 6))
        self.reward_count = tk.Frame(head, bg=ui.SURFACE)
        self.reward_count.pack(side="left")
        self.reward_grid = tk.Frame(rw.body, bg=ui.SURFACE)
        self.reward_grid.pack(fill="x")
        self._rewards_version = self.state.get("rewards_version", 0)


    def _build_music_card(self, parent):
        ctl = self.state.get("music")
        mus = self._card(parent, t("musicaTitulo"), info=t("musicaAviso"))
        mus.pack(fill="x", pady=(0, 14))
        if not music.AVAILABLE:
            ui.Notice(mus.body, "error").pack(fill="x", pady=(0, 8))
            mus.body.winfo_children()[-1].set(t("musicaNoDisp"), "error")
        self.preset_vars = {}
        grid = tk.Frame(mus.body, bg=ui.SURFACE)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        names = [t(music.CATALOG[i][0]) for i in music.CATALOG_ORDER]
        by_mode = self.cfg.get("music_by_mode", {})
        for r, (code, label_key) in enumerate((("T", "tipoTemporizador"), ("C", "tipoCronometro"),
                                               ("W", "tipoPomodoroTrabajo"), ("D", "tipoPomodoroDescanso"))):
            self._lbl(grid, t(label_key), "body").grid(row=r, column=0, sticky="w", padx=(0, 12), pady=4)
            cur = by_mode.get(code, "none")
            var = tk.StringVar(value=t(music.CATALOG[cur][0]) if cur in music.CATALOG else names[0])
            cb = ui.combobox(grid, var, names)
            cb.grid(row=r, column=1, sticky="we", pady=4)
            cb.bind("<<ComboboxSelected>>", lambda e: self._save_music())
            self.preset_vars[code] = var
        vol = tk.Frame(mus.body, bg=ui.SURFACE)
        vol.pack(fill="x", pady=(10, 0))
        self._lbl(vol, t("volumen"), "body").pack(side="left", padx=(0, 12))
        self.vol_var = tk.DoubleVar(value=round(self.cfg.get("music_volume", 0.35) * 100))
        self.vol_out = self._lbl(vol, f"{int(self.vol_var.get())}%", "muted")
        self.vol_out.pack(side="right")
        from tkinter import ttk
        sc = ttk.Scale(vol, from_=0, to=100, variable=self.vol_var, style="App.Horizontal.TScale",
                       command=self._on_volume)
        sc.pack(side="left", fill="x", expand=True)
        sc.bind("<ButtonRelease-1>", lambda e: self._save_music())
        self.auto_start = tk.BooleanVar(value=self.cfg.get("music_auto_start", True))
        self.auto_stop = tk.BooleanVar(value=self.cfg.get("music_auto_stop", True))
        ui.checkbutton(mus.body, t("musicaAuto"), self.auto_start, command=self._save_music).pack(fill="x", pady=(10, 0))
        ui.checkbutton(mus.body, t("musicaStop"), self.auto_stop, command=self._save_music).pack(fill="x")
        # --- sonido de aviso (fin de sesión / cambio de modo)
        self.sound_on = tk.BooleanVar(value=self.cfg.get("sound_end", True))
        ui.checkbutton(mus.body, t("sonidoAviso"), self.sound_on, command=self._save_sound).pack(fill="x", pady=(14, 0))
        svol = tk.Frame(mus.body, bg=ui.SURFACE)
        svol.pack(fill="x", pady=(6, 0))
        self._lbl(svol, t("volumen"), "body").pack(side="left", padx=(0, 12))
        self.svol_var = tk.DoubleVar(value=round(self.cfg.get("sound_volume", 0.6) * 100))
        self.svol_out = self._lbl(svol, f"{int(self.svol_var.get())}%", "muted")
        self.svol_out.pack(side="right")
        ssc = ttk.Scale(svol, from_=0, to=100, variable=self.svol_var, style="App.Horizontal.TScale",
                        command=lambda _v=None: self.svol_out.configure(text=f"{int(self.svol_var.get())}%"))
        ssc.pack(side="left", fill="x", expand=True)
        ssc.bind("<ButtonRelease-1>", lambda e: self._save_sound())
        ui.Button(mus.body, t("btnProbarSonido"), self._try_sound, style="ghost").pack(anchor="w", pady=(8, 0))
        bar = tk.Frame(mus.body, bg=ui.SURFACE)
        bar.pack(fill="x", pady=(12, 0))
        ui.Button(bar, t("btnProbarMusica"), self._try_music, style="ghost").pack(side="left")
        ui.Button(bar, t("btnDetenerMusica"), lambda: ctl and ctl.stop(), style="ghost").pack(side="left", padx=8)
        self.music_status = self._lbl(bar, "", "muted")
        self.music_status.pack(side="right")


    def _on_volume(self, _v=None):
        vol = self.vol_var.get() / 100
        self.vol_out.configure(text=f"{int(self.vol_var.get())}%")
        ctl = self.state.get("music")
        if ctl:
            ctl.set_volume(vol)

    def _save_music(self):
        ids = {t(music.CATALOG[i][0]): i for i in music.CATALOG_ORDER}
        self._save_cfg(
            music_by_mode={c: ids.get(v.get(), "none") for c, v in self.preset_vars.items()},
            music_volume=round(self.vol_var.get() / 100, 2),
            music_auto_start=bool(self.auto_start.get()), music_auto_stop=bool(self.auto_stop.get()))

    def _save_sound(self):
        self._save_cfg(sound_end=bool(self.sound_on.get()), sound_volume=round(self.svol_var.get() / 100, 2))

    def _save_strict(self):
        """Guarda el modo estricto. Con una sesión en marcha no se puede cambiar ni apagar; para apagarlo hay que
        escribir un código aleatorio distinto cada vez."""
        was_on, was_n = bool(self.cfg.get("strict_mode")), int(self.cfg.get("strict_confirms", 3))
        on = bool(self.strict_var.get())
        n = guard.clamp_confirms(self.strict_n.get(), was_n)
        self.strict_n.set(str(n))
        if on == was_on and n == was_n:
            return
        if guard.settings_locked(self.cfg, getattr(self, "_live_estado", None)):
            self.strict_var.set(was_on)
            self.strict_n.set(str(was_n))
            self.strict_notice.set(t("estrictoBloqueado"), "error")
            return
        if was_on and not on and not ui.ask_code(self.top, t("estrictoCodigoTitulo"), t("estrictoCodigoTexto"),
                                                 guard.new_code(), t("estrictoCodigoBoton"), t("cancelar"),
                                                 t("estrictoCodigoMal")):
            self.strict_var.set(True)
            return
        self.strict_notice.set("", "success")
        self._save_cfg(strict_mode=on, strict_confirms=n)

    def _save_strict_code(self):
        """«Pedir código al terminar antes»: no se puede cambiar mientras hay una sesión en marcha."""
        if self._session_running():
            self.strict_code_var.set(bool(self.cfg.get("strict_stop_code", False)))
            self.strict_notice.set(t("estrictoBloqueado"), "error")
            return
        self.strict_notice.set("", "success")
        self._save_cfg(strict_stop_code=bool(self.strict_code_var.get()))

    def _sync_strict_lock(self):
        """Deshabilita los controles del modo estricto y del bloqueo mientras hay una sesión en marcha."""
        if hasattr(self, "block_timer_chk"):
            try:
                st = ["disabled"] if guard.block_settings_locked(getattr(self, "_live_estado", None), self.cfg) else ["!disabled"]
                self.block_timer_chk.state(st)
                self.block_chrono_chk.state(["disabled"] if getattr(self, "_live_estado", None) and self._live_estado.get("ejecutando")
                                            else ["!disabled"])
            except tk.TclError:
                pass
        if not hasattr(self, "strict_chk"):
            return
        try:
            self.strict_code_chk.state(["disabled"] if self._session_running() else ["!disabled"])
        except tk.TclError:
            pass
        locked = guard.settings_locked(self.cfg, getattr(self, "_live_estado", None))
        try:
            self.strict_chk.state(["disabled"] if locked else ["!disabled"])
            self.strict_sp.state(["disabled"] if locked else ["!disabled"])
        except tk.TclError:
            pass

    def _try_sound(self):
        import chime
        if not chime.AVAILABLE:
            self.music_status.configure(text=t("musicaNoDisp"))
            return
        chime.play("done", self.svol_var.get() / 100)

    def _try_music(self):
        ctl = self.state.get("music")
        if not ctl:
            return
        estado = self.state.get("estado")
        key = music.music_key(estado) or "T"
        preset = self.cfg.get("music_by_mode", {}).get(key, "brown")
        ctl.play(preset if preset != "none" else "brown", self.cfg.get("music_volume", 0.35))

    def _offline_use_noise(self):
        ctl = self.state.get("music")
        if ctl:
            ctl.play("brown", self.cfg.get("music_volume", 0.35))

    def _offline_retry(self):
        ctl = self.state.get("music")
        if ctl and ctl.offline:
            ctl.play(ctl.offline, ctl.volume)

    def _render_music_offline(self):
        """Banner grande en el Panel mientras la radio elegida no pueda sonar por falta de internet."""
        ctl = self.state.get("music")
        off = getattr(ctl, "offline", "") if ctl else ""
        if not hasattr(self, "offline_banner"):
            return
        try:
            if off and off in music.CATALOG:                     # el texto solo se toca cuando cambia (evita reflujos)
                body = t("musicaOfflineCuerpo", radio=t(music.CATALOG[off][0]))
                if getattr(self, "_offline_text", None) != body:
                    self._offline_text = body
                    self.offline_body.configure(text=body)
            if bool(off) == self._offline_shown:
                return
            self._offline_shown = bool(off)
            if off:
                self.offline_banner.pack(fill="x", pady=(0, 14), before=self.live["card"])
            else:
                self.offline_banner.pack_forget()
        except tk.TclError:
            pass

    def _render_music_status(self):
        self._render_music_offline()
        if "ajustes" not in self.built or not hasattr(self, "music_status"):
            return
        ctl = self.state.get("music")
        if not ctl:
            return
        if getattr(ctl, "offline", ""):
            txt = "📡 " + t("musicaOfflineTitulo")
        elif ctl.current:
            txt = f"{t('musicaActual')}: {t(music.CATALOG[ctl.current][0])}"
        elif ctl.error and ctl.error != "miniaudio":
            txt = t("musicaErrorDisp") + ctl.error
        else:
            txt = f"{t('musicaActual')}: {t('musicaNada')}"
        try:
            self.music_status.configure(text=txt)
        except tk.TclError:
            pass

    def _save_cats(self):
        chosen = [c for c in rewards.CATEGORY_ORDER if self.cat_vars[c].get()] or ["trenes"]
        self._save_cfg(reward_categories=chosen)

    def _open_logros(self, _e=None):
        self.tabs.set("premios")
        self._on_tab("premios")

    def _render_trophy_strip(self):
        box = getattr(self, "trophy_strip", None)
        if box is None or not box.winfo_exists():
            return
        import insights
        import tasks
        import trophies
        pieces = load_data().get("rewards", [])
        for w in box.winfo_children():
            w.destroy()
        top = tk.Frame(box, bg=ui.SURFACE, cursor="hand2")
        top.pack(fill="x")
        self._lbl(top, "🏆 " + t("nPiezas", n=len(pieces)), "bold", cursor="hand2").pack(side="left")
        tot = insights.totals(self.log or [], tasks.done_by_date(tasks.load()))
        got, total, nxt = trophies.overall(tot)
        self._lbl(top, t("statLogrosCuenta", a=got, b=total), "muted", cursor="hand2").pack(side="right")
        tiles = tk.Frame(box, bg=ui.SURFACE, cursor="hand2")
        tiles.pack(fill="x", pady=(8, 0))
        self._strip_photos = []
        size = 34
        for p in list(reversed(pieces))[:8]:
            tile = tk.Canvas(tiles, width=size, height=size, bg=ui.SURFACE, highlightthickness=0, bd=0, cursor="hand2")
            ui.round_rect(tile, 1, 1, size - 1, size - 1, 9, fill=p["color"], outline=p["color"])
            ph = emoji_img.photo(p["icon"], 22)
            if ph is not None:
                self._strip_photos.append(ph)
                tile.create_image(size / 2, size / 2, image=ph)
            else:                                           # sin imagen: el emoji como texto (igual que en Premios)
                tile.create_text(size / 2, size / 2, text=p["icon"], font=(ui.F("body")[0], 14), fill="#ffffff")
            tile.pack(side="left", padx=(0, 4))
            ui.Tooltip(tile, rewards.piece_name(p, i18n.get("piezaNombres")))
        if not pieces:
            self._lbl(tiles, t("sinPiezas"), "muted", wraplength=330, cursor="hand2").pack(fill="x")
        if nxt:
            fam, goal, _v = nxt
            self._lbl(box, t("panelLogro", name=t("logro_" + fam, n=goal)), "muted", wraplength=330,
                      cursor="hand2").pack(fill="x", pady=(8, 0))

        def bind(w):
            w.bind("<Button-1>", self._open_logros)
            for c in w.winfo_children():
                bind(c)
        bind(box)

    def _show_toast(self, text):
        old = getattr(self, "_toast_w", None)
        if old is not None:
            try:
                old.destroy()
            except tk.TclError:
                pass
        lab = tk.Label(self.top, text=text, bg=ui.ACCENT, fg=ui.WHITE if ui.lum(ui.ACCENT) < 0.6 else ui.INK,
                       font=ui.F("bold"), padx=18, pady=10, wraplength=520, cursor="hand2")
        lab.place(relx=0.5, y=14, anchor="n")
        lab.lift()
        lab.bind("<Button-1>", lambda e: (self._open_logros(), lab.destroy()))
        self._toast_w = lab
        self.top.after(5200, lambda: lab.winfo_exists() and lab.destroy())

    def _render_rewards(self):
        self._render_trophy_strip()
        if "premios" not in self.built:
            return
        pieces = load_data().get("rewards", [])
        import achievements_gui
        import tasks
        sig = (len(self.log or []), (self.log[-1].get("epoch") if self.log else 0), len(pieces),
               sum(tasks.done_by_date(tasks.load()).values()), ui.THEME, ui.PALETTE, ui.TEXT_SCALE)
        if sig != getattr(self, "_logros_sig", None):
            self._logros_sig = sig
            achievements_gui.build(self, self.achievements_host)
        for w in self.reward_count.winfo_children():
            w.destroy()
        ui.Pill(self.reward_count, t("nPiezas", n=len(pieces))).pack()
        g = self.reward_grid
        for w in g.winfo_children():
            w.destroy()
        self.photos = []
        if not pieces:
            self._lbl(g, t("sinPiezas"), "muted").pack(fill="x")
            return
        per_row, size = 10, 62
        for i, p in enumerate(list(reversed(pieces))[:120]):
            tile = tk.Canvas(g, width=size, height=size, bg=ui.SURFACE, highlightthickness=0, bd=0)
            ui.round_rect(tile, 1, 1, size - 1, size - 1, 14, fill=p["color"], outline=p["color"])
            ph = emoji_img.photo(p["icon"], 38)
            if ph is not None:
                self.photos.append(ph)
                tile.create_image(size / 2, size / 2, image=ph)
            else:
                tile.create_text(size / 2, size / 2, text=p["icon"], font=(ui.F("body")[0], 20), fill="#ffffff")
            tile.grid(row=i // per_row, column=i % per_row, padx=3, pady=3)
            ui.Tooltip(tile, rewards.piece_name(p, i18n.get("piezaNombres")))

    # ------------------------------------------------------------------ AJUSTES
    def _build_ajustes(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        sections = [("general", t("ajSecGeneral")), ("apariencia", t("ajSecApariencia")),
                    ("mascota", t("ajSecMascota")), ("temporizador", t("ajSecTemporizador")), ("bloqueo", t("ajSecBloqueo")), ("musica", t("ajSecMusica")),
                    ("avanzado", t("ajSecAvanzado"))]
        self._aj_frames, cols = {}, {}
        for key, _ in sections:
            fr = tk.Frame(parent, bg=ui.CANVAS)
            fr.columnconfigure(0, weight=1, uniform="aj")
            fr.columnconfigure(1, weight=1, uniform="aj")
            a, b = tk.Frame(fr, bg=ui.CANVAS), tk.Frame(fr, bg=ui.CANVAS)
            a.grid(row=0, column=0, sticky="new", padx=(0, 7))
            b.grid(row=0, column=1, sticky="new", padx=(7, 0))
            self._aj_frames[key], cols[key] = fr, (a, b)

        def show_section(key):
            _open["ajsec"] = key
            for k, fr in self._aj_frames.items():
                fr.grid_forget()
            self._aj_frames[key].grid(row=2, column=0, columnspan=2, sticky="new")
        cur_sec = _open.get("ajsec") if _open.get("ajsec") in self._aj_frames else "general"
        self.aj_nav = ui.Segmented(parent, sections, cur_sec, show_section, padx=12)
        self.aj_nav.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))
        col0, col1 = cols["general"]

        # Inicio automático con el sistema (arriba, a la vista)
        st = self._card(col0, t("subInicio"))
        st.pack(fill="x", pady=(0, 14))
        self.autostart_var = tk.BooleanVar(value=self._autostart_on())
        ui.checkbutton(st.body, t("inicioSistema"), self.autostart_var, command=self._toggle_autostart).pack(fill="x")
        self._lbl(st.body, t("inicioSistemaAyuda"), "muted", wraplength=380).pack(fill="x", pady=(6, 0))
        self.startup_tasks_var = tk.BooleanVar(value=bool(self.cfg.get("startup_tasks", False)))
        ui.checkbutton(st.body, t("subInicioTareas"), self.startup_tasks_var,
                       command=lambda: self._save_cfg(startup_tasks=bool(self.startup_tasks_var.get()))).pack(fill="x", pady=(8, 0))
        self.autostart_notice = ui.Notice(st.body, "error")
        self.autostart_notice.pack(fill="x", pady=(6, 0))

        # Días de la racha
        sk = self._card(col0, t("subRachaDias"))
        sk.pack(fill="x", pady=(0, 14))
        self._lbl(sk.body, t("rachaDiasAyuda"), "muted", wraplength=380).pack(fill="x", pady=(0, 8))
        from tasks_gui import DayChip
        row = tk.Frame(sk.body, bg=ui.SURFACE)
        row.pack(fill="x")
        self._streak_chips = []
        sel = set(stats.streak_days(self.cfg))
        for i, letter in enumerate(i18n.get("diasSemanaCorto")):
            chip = DayChip(row, letter, i in sel, lambda i=i: self._toggle_streak_day(i))
            chip.pack(side="left", padx=(0, 6))
            self._streak_chips.append(chip)

        # Modo de funcionamiento + conexión
        local = self.cfg.get("connection_mode") == "local"
        c = self._card(col0, t("subModo"), info=(t("modoLocalAyuda") if local else t("modoDispositivoAyuda")))
        c.pack(fill="x", pady=(0, 14))
        self.mode_seg = ui.Segmented(c.body, [("device", t("modoDispositivo")), ("local", t("modoLocal"))],
                                     "local" if local else "device", self._change_connection_mode, padx=14)
        self.mode_seg.pack(anchor="w")
        self.url_var = tk.StringVar(value=self.cfg.get("esp_url", ""))
        self.conn_notice = ui.Notice(c.body, "success")
        if not local:
            self._lbl(c.body, t("subConexion"), "bold").pack(fill="x", pady=(12, 4))
            ui.entry(c.body, self.url_var).pack(fill="x")
            ui.Button(c.body, t("guardar"), self._save_url).pack(anchor="w", pady=(8, 0))
            self._lbl(c.body, t("dirEspAyuda") + " " + t("ayudaConfigWifi"), "muted", wraplength=380).pack(fill="x", pady=(8, 0))
            self.conn_notice.pack(fill="x", pady=(8, 0))

        # Apariencia + idioma
        col0, col1 = cols["apariencia"]
        a = self._card(col0, t("subApariencia"))
        a.pack(fill="x", pady=(0, 14))
        ui.Segmented(a.body, [("light", t("temaClaro")), ("dark", t("temaOscuro")), ("system", t("temaSistema"))],
                     self.cfg.get("theme", "system"), self._change_theme).pack(anchor="w")
        self._lbl(a.body, t("tamTexto"), "bold").pack(fill="x", pady=(12, 6))
        cur = min((0.9, 1.0, 1.15, 1.3), key=lambda v: abs(v - float(self.cfg.get("text_scale", 1.0) or 1.0)))
        ui.Segmented(a.body, [("0.9", t("tamPeq")), ("1.0", t("tamNormal")), ("1.15", t("tamGrande")),
                              ("1.3", t("tamMuyGrande"))], str(cur), self._change_text_scale).pack(anchor="w")
        self._lbl(a.body, t("subIdioma"), "bold").pack(fill="x", pady=(12, 6))
        names = {code: name for code, name in i18n.LANGS}
        self.lang_var = tk.StringVar(value=names.get(self.cfg.get("language", "es"), "Español"))
        cb = ui.combobox(a.body, self.lang_var, [name for _c, name in i18n.LANGS])
        cb.pack(anchor="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._change_language(
            next((c for c, n in i18n.LANGS if n == self.lang_var.get()), "es")))

        # Tema de color
        self._build_theme_card(col0)

        # Música (antes vivía en la pestaña de premios)
        self._build_music_card(cols["musica"][0])

        # Comportamiento
        col0, col1 = cols["general"]
        b = self._card(col0, t("subComportamiento"), info=t("estrictoAviso"))
        b.pack(fill="x", pady=(0, 14))
        self.confirm_var = tk.BooleanVar(value=bool(self.cfg.get("confirm_stop", True)))
        ui.checkbutton(b.body, t("confirmarStopLabel"), self.confirm_var,
                       command=lambda: self._save_cfg(confirm_stop=bool(self.confirm_var.get()))).pack(fill="x")
        self.strict_var = tk.BooleanVar(value=bool(self.cfg.get("strict_mode", False)))
        self.strict_chk = ui.checkbutton(b.body, t("estrictoLabel"), self.strict_var, command=self._save_strict)
        self.strict_chk.pack(fill="x", pady=(8, 0))
        srow = tk.Frame(b.body, bg=ui.SURFACE)
        srow.pack(fill="x", pady=(4, 0), padx=(24, 0))
        self._lbl(srow, t("estrictoVeces"), "muted").pack(side="left")
        self.strict_n = tk.StringVar(value=str(self.cfg.get("strict_confirms", 3)))
        sp = self.strict_sp = ui.spinbox(srow, self.strict_n, 1, 100, width=5)
        sp.configure(command=self._save_strict)
        sp.pack(side="right")
        sp.bind("<FocusOut>", lambda e: self._save_strict())
        sp.bind("<Return>", lambda e: self._save_strict())
        self.strict_code_var = tk.BooleanVar(value=bool(self.cfg.get("strict_stop_code", False)))
        self.strict_code_chk = ui.checkbutton(b.body, t("estrictoCodigoStop"), self.strict_code_var,
                                              command=self._save_strict_code)
        self.strict_code_chk.pack(fill="x", pady=(6, 0), padx=(24, 0))
        self.strict_notice = ui.Notice(b.body, "error")
        self.strict_notice.pack(fill="x", pady=(6, 0))
        self._sync_strict_lock()
        self.confetti_var = tk.BooleanVar(value=bool(self.cfg.get("confetti", True)))
        more = self._collapsible(b.body, t("masOpciones"))
        row = tk.Frame(more, bg=ui.SURFACE)
        row.pack(fill="x", pady=(8, 0))
        ui.checkbutton(row, t("confetiLabel"), self.confetti_var,
                       command=lambda: self._save_cfg(confetti=bool(self.confetti_var.get()))).pack(side="left")
        ui.Button(row, t("confetiProbar"), self.celebrate, style="ghost", padx=10, pady=4).pack(side="right")
        mb = self._card(cols["mascota"][0], t("subMascota"), info=t("mascotaInfo"))
        mb.pack(fill="x", pady=(0, 14))
        self.mascot_var = tk.BooleanVar(value=bool(self.cfg.get("mascot", True)))
        ui.checkbutton(mb.body, t("mascotaLabel"), self.mascot_var,
                       command=lambda: self._save_cfg(mascot=bool(self.mascot_var.get()))).pack(fill="x", pady=(0, 0))
        self.mascot_text_var = tk.BooleanVar(value=bool(self.cfg.get("mascot_text", True)))
        ui.checkbutton(mb.body, t("mascotaTexto"), self.mascot_text_var,
                       command=lambda: self._save_cfg(mascot_text=bool(self.mascot_text_var.get()))).pack(fill="x", pady=(4, 0), padx=(24, 0))
        self.mascot_top_var = tk.BooleanVar(value=bool(self.cfg.get("mascot_on_top", True)))
        ui.checkbutton(mb.body, t("mascotaAlFrente"), self.mascot_top_var,
                       command=lambda: self._save_cfg(mascot_on_top=bool(self.mascot_top_var.get()))).pack(fill="x", pady=(4, 0), padx=(24, 0))
        mcol = tk.Frame(mb.body, bg=ui.SURFACE)
        mcol.pack(fill="x", pady=(6, 0), padx=(24, 0))
        self._lbl(mcol, t("mascotaColor"), "body").pack(side="left", padx=(0, 12))
        self._mascot_swatches = {}
        import mascot as _mascot

        def pick_color(name):
            self._save_cfg(mascot_color=name)
            for n, sw in self._mascot_swatches.items():
                sw.configure(highlightbackground=ui.INK if n == name else ui.SURFACE)
        current = self.cfg.get("mascot_color", "peach")
        for name, pal in _mascot.PALETTES.items():
            sw = tk.Frame(mcol, bg=pal[0], width=22, height=22, cursor="hand2", highlightthickness=2,
                          highlightbackground=ui.INK if name == current else ui.SURFACE)
            sw.pack(side="left", padx=2)
            sw.bind("<Button-1>", lambda e, n=name: pick_color(n))
            self._mascot_swatches[name] = sw
        msz = tk.Frame(mb.body, bg=ui.SURFACE)
        msz.pack(fill="x", pady=(4, 0), padx=(24, 0))
        self._lbl(msz, t("mascotaTamano"), "body").pack(side="left", padx=(0, 12))
        self.msize_var = tk.DoubleVar(value=self.cfg.get("mascot_size", 110))
        self.msize_out = self._lbl(msz, f"{int(self.msize_var.get())} px", "muted")
        self.msize_out.pack(side="right")
        msc = ttk.Scale(msz, from_=56, to=240, variable=self.msize_var, style="App.Horizontal.TScale",
                        command=lambda _v=None: self.msize_out.configure(text=f"{int(self.msize_var.get())} px"))
        msc.pack(side="left", fill="x", expand=True)
        msc.bind("<ButtonRelease-1>", lambda e: self._save_cfg(mascot_size=int(self.msize_var.get())))
        mfs = tk.Frame(mb.body, bg=ui.SURFACE)
        mfs.pack(fill="x", pady=(4, 0), padx=(24, 0))
        self._lbl(mfs, t("mascotaLetra"), "body").pack(side="left", padx=(0, 12))
        self.mfont_var = tk.DoubleVar(value=self.cfg.get("mascot_font", 10))
        self.mfont_out = self._lbl(mfs, f"{int(self.mfont_var.get())} pt", "muted")
        self.mfont_out.pack(side="right")
        mfc = ttk.Scale(mfs, from_=8, to=22, variable=self.mfont_var, style="App.Horizontal.TScale",
                        command=lambda _v=None: self.mfont_out.configure(text=f"{int(self.mfont_var.get())} pt"))
        mfc.pack(side="left", fill="x", expand=True)
        mfc.bind("<ButtonRelease-1>", lambda e: self._save_cfg(mascot_font=int(self.mfont_var.get())))
        try:
            days = stats.streak(stats.calendar_counts([s for s in getattr(self, "log", []) if s.get("modo") != "D"]), None, stats.streak_days(self.cfg))
        except Exception:
            days = 0
        self._lbl(mb.body, t("mascotaCrece", n=days), "muted", wraplength=420).pack(fill="x", pady=(8, 0), padx=(24, 0))
        ui.Button(mb.body, t("mascotaReset"), lambda: self._save_cfg(mascot_x=None, mascot_y=None), style="ghost",
                  padx=10, pady=4).pack(anchor="w", pady=(6, 0), padx=(24, 0))
        self.eco_var = tk.BooleanVar(value=bool(self.cfg.get("eco_mode", False)))
        ui.checkbutton(more, t("ecoLabel"), self.eco_var,
                       command=lambda: self._save_cfg(eco_mode=bool(self.eco_var.get()))).pack(fill="x", pady=(8, 0))
        self._lbl(more, t("ecoInfo"), "muted", wraplength=420).pack(fill="x", padx=(24, 0))
        self.adaptive_var = tk.BooleanVar(value=bool(self.cfg.get("adaptive", True)))
        ui.checkbutton(more, t("adaptarLabel"), self.adaptive_var,
                       command=lambda: (self._save_cfg(adaptive=bool(self.adaptive_var.get())), self._render_help())).pack(fill="x", pady=(8, 0))
        self.minimize_session_var = tk.BooleanVar(value=bool(self.cfg.get("minimize_on_session", False)))
        ui.checkbutton(more, t("minimizarSesion"), self.minimize_session_var,
                       command=lambda: self._save_cfg(minimize_on_session=bool(self.minimize_session_var.get()))).pack(fill="x", pady=(8, 0))
        self.minimize_var = tk.BooleanVar(value=bool(self.cfg.get("minimize_on_task", False)))
        ui.checkbutton(more, t("minimizarTarea"), self.minimize_var,
                       command=lambda: self._save_cfg(minimize_on_task=bool(self.minimize_var.get()))).pack(fill="x", pady=(8, 0))

        # Avanzado: puente con la extensión del navegador
        adv = self._card(cols["avanzado"][0], t("puenteTitulo"), info=t("puenteAyuda"))
        adv.pack(fill="x", pady=(0, 14))
        self.bridge_var = tk.BooleanVar(value=bool(self.cfg.get("bridge", True)))
        ui.checkbutton(adv.body, t("puenteExtension"), self.bridge_var,
                       command=self._toggle_bridge).pack(fill="x")
        prow = tk.Frame(adv.body, bg=ui.SURFACE)
        prow.pack(fill="x", pady=(12, 0))
        self._lbl(prow, t("puertoLabel"), "muted", wraplength=250).pack(side="left", fill="x", expand=True)
        self.port_var = tk.StringVar(value=str(self.cfg.get("bridge_port", 8765)))
        pe = ui.spinbox(prow, self.port_var, 1024, 65535, width=7)
        pe.pack(side="right")
        pe.bind("<Return>", lambda e: self._save_port())
        brow = tk.Frame(adv.body, bg=ui.SURFACE)
        brow.pack(fill="x", pady=(10, 0))
        ui.Button(brow, t("guardar"), self._save_port).pack(side="left")
        ui.Button(brow, t("puertoRestablecer"), lambda: (self.port_var.set("8765"), self._save_port()),
                  style="ghost").pack(side="left", padx=8)
        self.port_notice = ui.Notice(adv.body, "success")
        self.port_notice.pack(fill="x", pady=(8, 0))

        # Colores
        k = self._card(cols["apariencia"][1], t("subColores"))
        k.pack(fill="x", pady=(0, 14))
        self.swatches = {}
        row = tk.Frame(k.body, bg=ui.SURFACE)
        row.pack(fill="x")
        for code, key in (("T", "colorTemporizador"), ("C", "colorCronometro"), ("P", "colorPomodoro")):
            col = tk.Frame(row, bg=ui.SURFACE)
            col.pack(side="left", padx=(0, 18))
            self._lbl(col, t(key), "muted").pack(anchor="w")
            sw = ui.Swatch(col, self._mc(code), lambda c=code: self._pick_color(c))
            sw.pack(anchor="w", pady=(4, 0))
            self.swatches[code] = sw
        brow = tk.Frame(k.body, bg=ui.SURFACE)
        brow.pack(fill="x", pady=(12, 0))
        ui.Button(brow, t("guardarColores"), self._save_colors, style="ghost").pack(side="left")
        ui.Button(brow, t("coloresDelTema"), self._reset_colors, style="plain").pack(side="left", padx=(8, 0))

        # Etiquetas
        tg = self._card(cols["general"][1], t("subEtiquetas"), info=t("etiquetasAviso"))
        tg.pack(fill="x", pady=(0, 14))
        row = tk.Frame(tg.body, bg=ui.SURFACE)
        row.pack(fill="x")
        self.tag_var = tk.StringVar()
        e = ui.entry(row, self.tag_var)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self._add_tag())
        ui.Button(row, t("agregar"), self._add_tag, style="ghost").pack(side="left", padx=(8, 0))
        self.tag_list = tk.Frame(tg.body, bg=ui.SURFACE)
        self.tag_list.pack(fill="x", pady=(8, 0))

        # Frases
        fr = self._card(cols["mascota"][1], t("subFrases"), info=t("frasesAviso"))
        fr.pack(fill="x", pady=(0, 14))
        row = tk.Frame(fr.body, bg=ui.SURFACE)
        row.pack(fill="x")
        self.phrase_var = tk.StringVar()
        e = ui.entry(row, self.phrase_var)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self._add_phrase())
        ui.Button(row, t("agregar"), self._add_phrase, style="ghost").pack(side="left", padx=(8, 0))
        self.phrase_list = tk.Frame(fr.body, bg=ui.SURFACE)
        self.phrase_list.pack(fill="x", pady=(8, 0))

        # Nombre
        n = self._card(cols["mascota"][1], t("subTuNombre"))
        n.pack(fill="x", pady=(0, 14))
        row = tk.Frame(n.body, bg=ui.SURFACE)
        row.pack(fill="x")
        self.name_var = tk.StringVar(value=self.cfg.get("user_name", ""))
        e = ui.entry(row, self.name_var)
        e.pack(side="left", fill="x", expand=True)
        ui.Button(row, t("guardar"), self._save_name, style="ghost").pack(side="left", padx=(8, 0))

        # Dispositivo
        d = self._card(cols["temporizador"][0], t("subDuraciones") if local else t("subAjustesESP"), info=t("configAvisoLocal") if local else t("configAviso"))
        d.pack(fill="x")
        self.dev_vars = {}
        fields = [("minutos", "labelMinutos", 1, 99), ("brillo", "labelBrillo", 0, 7),
                  ("pomTrabajo", "labelPomTrabajo", 1, 99), ("pomDescanso", "labelPomDescanso", 1, 99),
                  ("pomDescansoLargo", "labelPomDescansoLargo", 1, 99), ("pomCiclos", "labelPomCiclos", 1, 10)]
        if local:
            fields = [f for f in fields if f[0] != "brillo"]
        for key, label_key, lo, hi in fields:
            row = tk.Frame(d.body, bg=ui.SURFACE)
            row.pack(fill="x", pady=3)
            self._lbl(row, t(label_key), "muted", wraplength=270).pack(side="left", fill="x", expand=True)
            var = tk.StringVar(value="")
            self.dev_vars[key] = var
            sb = ui.spinbox(row, var, lo, hi, width=5)
            sb.pack(side="right")
            self._enter_esc(sb, self._save_device, self._load_device)
        self.auto_wifi = tk.BooleanVar(value=False)
        if not local:
            ui.checkbutton(d.body, t("labelAutoWiFi"), self.auto_wifi).pack(fill="x", pady=(8, 0))
        ui.Button(d.body, t("guardarConfig"), self._save_device).pack(anchor="w", pady=(12, 0))
        self.dev_notice = ui.Notice(d.body, "success")
        self.dev_notice.pack(fill="x", pady=(8, 0))
        self._build_goals_card(cols["temporizador"][1])
        self._build_block_card(cols["bloqueo"][0])
        self._build_data_card(cols["avanzado"][1])
        show_section(cur_sec)
        self._render_lists()
        self._load_device()

    # ---- metas, bloqueo, datos
    def _build_goals_card(self, parent):
        g = self._card(parent, t("metasTitulo"), info=t("metasAviso"))
        g.pack(fill="x", pady=(0, 14))
        self.goal_vars = {}
        for key, label, lo, hi in (("goal_daily_min", "metaDiaria", 0, 1440), ("goal_weekly_min", "metaSemanal", 0, 10080),
                                   ("warn_end_min", "metaAvisoPrevio", 0, 60)):
            row = tk.Frame(g.body, bg=ui.SURFACE)
            row.pack(fill="x", pady=3)
            self._lbl(row, t(label), "muted", wraplength=270).pack(side="left", fill="x", expand=True)
            var = tk.StringVar(value=str(self.cfg.get(key, 0)))
            self.goal_vars[key] = var
            ui.spinbox(row, var, lo, hi, width=6).pack(side="right")
        ui.Button(g.body, t("guardar"), self._save_goals).pack(anchor="w", pady=(12, 0))
        self.goal_notice = ui.Notice(g.body, "success")
        self.goal_notice.pack(fill="x", pady=(8, 0))

    def _save_goals(self):
        vals = {}
        for key, var in self.goal_vars.items():
            try:
                vals[key] = max(0, int(var.get()))
            except ValueError:
                vals[key] = 0
        self._save_cfg(**vals)
        self.cfg = load_config()
        for key, var in self.goal_vars.items():
            var.set(str(self.cfg.get(key, 0)))
        self.goal_notice.set(t("guardado"), "success")
        self._render_calendar()

    def _build_block_card(self, parent):
        b = self._card(parent, t("bloqueoCardTitulo"), info=t("bloqueoCardAviso"))
        b.pack(fill="x", pady=(0, 14))
        if self.cfg.get("connection_mode") == "local":
            self.block_timer_var = tk.BooleanVar(value=bool(self.cfg.get("block_in_timer", True)))
            self.block_timer_chk = ui.checkbutton(b.body, t("bloqueoEnTemporizador"), self.block_timer_var,
                                                  command=lambda: self._save_cfg(block_in_timer=bool(self.block_timer_var.get())))
            self.block_timer_chk.pack(fill="x", pady=(0, 6))
            self.block_chrono_var = tk.BooleanVar(value=bool(self.cfg.get("block_in_chrono", False)))
            self.block_chrono_chk = ui.checkbutton(b.body, t("bloqueoEnCronometro"), self.block_chrono_var,
                                                   command=lambda: self._save_cfg(block_in_chrono=bool(self.block_chrono_var.get())))
            self.block_chrono_chk.pack(fill="x", pady=(0, 10))
        row = tk.Frame(b.body, bg=ui.SURFACE)
        row.pack(fill="x")
        ui.Button(row, t("btnBloqueo"), self._open_block).pack(side="left")
        ui.Button(row, t("btnSitios"), self._open_sites, style="ghost").pack(side="left", padx=8)

    def _build_data_card(self, parent):
        d = self._card(parent, t("datosTitulo"), info=t("datosAviso"))
        d.pack(fill="x", pady=(0, 14))
        row = tk.Frame(d.body, bg=ui.SURFACE)
        row.pack(fill="x")
        ui.Button(row, t("respaldoExportar"), self._export_backup).pack(side="left")
        ui.Button(row, t("respaldoImportar"), self._import_backup, style="ghost").pack(side="left", padx=8)
        row2 = tk.Frame(d.body, bg=ui.SURFACE)
        row2.pack(fill="x", pady=(8, 0))
        ui.Button(row2, t("descargarCSV"), self._export_csv, style="ghost").pack(side="left")
        ui.Button(row2, t("respaldoCarpeta"), self._open_data_dir, style="plain").pack(side="left", padx=8)
        self.data_notice = ui.Notice(d.body, "success")
        self.data_notice.pack(fill="x", pady=(10, 0))

    def _export_backup(self):
        import backup
        path = filedialog.asksaveasfilename(parent=self.top, defaultextension=".zip", initialfile=backup.default_name(),
                                            filetypes=[("ZIP", "*.zip")])
        if not path:
            return
        try:
            files = backup.export_zip(path)
            self.data_notice.set(t("respaldoGuardado", n=len(files)), "success")
        except OSError as exc:
            self.data_notice.set(str(exc), "error")

    def _import_backup(self):
        import backup
        if self._session_running():                       # restaurar ajustes antiguos soltaría el modo estricto y el bloqueo
            self.data_notice.set(t("respaldoBloqueado"), "error")
            return
        path = filedialog.askopenfilename(parent=self.top, filetypes=[("ZIP", "*.zip")])
        if not path:
            return
        try:
            backup.inspect(path)                           # valida antes de preguntar
        except ValueError:
            self.data_notice.set(t("respaldoInvalido"), "error")
            return
        if not ui.confirm(self.top, t("respaldoConfirmTitulo"), t("respaldoConfirmCuerpo"),
                          yes=t("respaldoRestaurar"), danger=True):
            return
        try:
            backup.restore_zip(path)
        except (ValueError, OSError):
            self.data_notice.set(t("respaldoInvalido"), "error")
            return
        self.data_notice.set(t("respaldoRestaurado"), "success")
        self.top.after(900, lambda: rebuild(self.root, self.state, self.lock, "ajustes"))

    def _open_data_dir(self):
        import subprocess, sys
        from config import config_dir
        folder = config_dir()
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)                       # noqa: S606 (carpeta propia de la app)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder], env=__import__("config").system_env())
        except Exception:
            self.data_notice.set(folder, "success")

    def _save_url(self):
        url = self.url_var.get().strip()
        if url and not url.startswith(("http://", "https://")):
            url = "http://" + url
            self.url_var.set(url)
        self._save_cfg(esp_url=url)
        self.conn_notice.set(t("guardado"), "success")
        self._refresh_log()
        self._load_device()

    def _change_connection_mode(self, mode):
        was_local = self.cfg.get("connection_mode") == "local"
        if mode == ("local" if was_local else "device"):
            return
        with self.lock:
            estado = self.state.get("estado")
        if estado and estado.get("ejecutando"):          # hay una sesión en curso: avisar antes de perderla
            if self.cfg.get("strict_mode") and not self._confirm_early_stop():
                self.mode_seg.set("local" if was_local else "device")
                return
            msg = t("modoCambioDeLocal") if was_local else t("modoCambioDeDispositivo")
            if not ui.confirm(self.top, t("modoCambioTitulo"), msg, yes=t("modoCambioSi"), danger=True):
                self.mode_seg.set("local" if was_local else "device")     # vuelve a la opción anterior
                return
            if was_local:                                   # la sesión propia termina (queda como incompleta)
                import local_timer
                local_timer.ENGINE.stop()
        self._save_cfg(connection_mode=mode)
        with self.lock:
            self.state["estado"] = None
            self.state["fast_until"] = time.time() + 3
        rebuild(self.root, self.state, self.lock, self.tab)

    def _change_text_scale(self, choice):
        self._save_cfg(text_scale=float(choice))
        ui.apply_text_scale(self.root, float(choice))
        rebuild(self.root, self.state, self.lock, self.tab)

    def _change_theme(self, choice):
        self._save_cfg(theme=choice)
        ui.apply_theme(choice, self.cfg.get("palette", "yopo"), self.cfg.get("custom_themes"))
        rebuild(self.root, self.state, self.lock, self.tab)

    # ---- tema de color
    def _build_theme_card(self, parent):
        import themes
        card = self._card(parent, t("subTemaColor"), info=t("temaColorAviso"))
        card.pack(fill="x", pady=(0, 14))
        grid = tk.Frame(card.body, bg=ui.SURFACE)
        grid.pack(fill="x")
        custom = self.cfg.get("custom_themes") or []
        items = [(None, t("temaYopo"), themes.DEFAULT_ID)] + [
            (th, th["name"], th["id"]) for th in themes.all_themes(custom)]
        current = ui.PALETTE
        for i, (th, name, tid) in enumerate(items):
            tile = ui.ThemeTile(grid, th, ui.THEME, name, tid == current,
                                lambda x=tid: self._change_palette(x))
            tile.grid(row=i // 3, column=i % 3, padx=(0, 8), pady=(0, 8))
        row = tk.Frame(card.body, bg=ui.SURFACE)
        row.pack(fill="x", pady=(2, 0))
        ui.Button(row, t("importarTema"), self._import_theme, style="ghost").pack(side="left")
        if any(c["id"] == current for c in custom):
            ui.Button(row, t("quitarTema"), self._remove_theme, style="danger").pack(side="left", padx=(8, 0))
        self.theme_notice = ui.Notice(card.body, "success")
        self.theme_notice.pack(fill="x", pady=(8, 0))

    def _change_palette(self, tid):
        self._save_cfg(palette=tid)
        ui.apply_theme(self.cfg.get("theme", "system"), tid, self.cfg.get("custom_themes"))
        rebuild(self.root, self.state, self.lock, self.tab)

    def _import_theme(self):
        import themes
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.top, title=t("importarTema"),
                                          filetypes=[("Theme", "*.theme"), ("*", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig") as f:
                theme = themes.parse_theme_file(f.read(2 ** 16))
        except (OSError, ValueError) as exc:
            self.theme_notice.set(t("temaInvalido") + f" ({exc})", "error")
            return
        custom = [c for c in (self.cfg.get("custom_themes") or []) if c["id"] != theme["id"]]
        if themes.find(theme["id"]):                      # no pisar uno incluido
            theme["id"] += "-2"
        custom.append(theme)
        self._save_cfg(custom_themes=custom[-20:], palette=theme["id"])
        ui.apply_theme(self.cfg.get("theme", "system"), theme["id"], self.cfg["custom_themes"])
        rebuild(self.root, self.state, self.lock, self.tab)

    def _remove_theme(self):
        cur = ui.PALETTE
        custom = [c for c in (self.cfg.get("custom_themes") or []) if c["id"] != cur]
        self._save_cfg(custom_themes=custom, palette="yopo")
        ui.apply_theme(self.cfg.get("theme", "system"), "yopo", custom)
        rebuild(self.root, self.state, self.lock, self.tab)

    def _reset_colors(self):
        self._save_cfg(mode_colors={"T": "", "C": "", "P": ""})
        for code, sw in self.swatches.items():
            sw.set(self._mc(code))
        self.estado_shown = object()
        self._render_calendar()

    def _change_language(self, code):
        self._save_cfg(language=code)
        i18n.set_language(code)
        url = esp_client.url_of(self.cfg)
        threading.Thread(target=esp_client.set_oled_language, args=(url, code), daemon=True).start()
        rebuild(self.root, self.state, self.lock, self.tab)

    def _save_name(self):
        self._save_cfg(user_name=self.name_var.get().strip()[:20])
        self.hero.set_title(self._greeting())
        self._render_calendar()

    def _pick_color(self, code):
        rgb, hexv = colorchooser.askcolor(color=self.swatches[code].color, parent=self.top, title=t("elegirColor"))
        if hexv:
            self.swatches[code].set(hexv)

    def _save_colors(self):
        self._save_cfg(mode_colors={c: sw.color for c, sw in self.swatches.items()})
        self.estado_shown = object()      # fuerza repintar el reloj
        self._render_calendar()

    # ---- etiquetas y frases
    def _add_tag(self):
        name = " ".join(self.tag_var.get().replace(",", " ").replace('"', "'").split())[:24]
        if name and name not in self.cfg["tags"]:
            self._save_cfg(tags=self.cfg["tags"] + [name])
        self.tag_var.set("")
        self._refresh_pending_options()
        self._render_lists()
        self._render_hist()

    def _del_tag(self, name):
        if not ui.confirm(self.top, t("borrarEtiquetaTitulo"), t("confirmBorrarEtiqueta", n=name), yes=t("borrar"), danger=True):
            return
        self._save_cfg(tags=[x for x in self.cfg["tags"] if x != name])
        self._refresh_pending_options()
        self._render_lists()
        self._render_hist()

    def _add_phrase(self):
        text = " ".join(self.phrase_var.get().replace('"', "'").split())[:120]
        if text:
            self._save_cfg(phrases=self.cfg["phrases"] + [text])
        self.phrase_var.set("")
        self._render_lists()
        self._render_calendar()

    def _del_phrase(self, idx):
        items = list(self.cfg["phrases"])
        if 0 <= idx < len(items):
            items.pop(idx)
            self._save_cfg(phrases=items)
        self._render_lists()
        self._render_calendar()

    def _render_lists(self):
        for frame in (self.tag_list, self.phrase_list):
            for w in frame.winfo_children():
                w.destroy()
        if not self.cfg["tags"]:
            self._lbl(self.tag_list, t("sinEtiquetas"), "muted").pack(fill="x")
        for name in self.cfg["tags"]:
            row = tk.Frame(self.tag_list, bg=ui.TAG_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=name, bg=ui.TAG_BG, fg=ui.INK, font=ui.F("small"), anchor="w").pack(
                side="left", padx=10, pady=5, fill="x", expand=True)
            x = tk.Label(row, text="✕", bg=ui.TAG_BG, fg=ui.MUTED, cursor="hand2", padx=8)
            x.pack(side="right")
            x.bind("<Button-1>", lambda e, n=name: self._del_tag(n))
        if not self.cfg["phrases"]:
            self._lbl(self.phrase_list, t("sinFrases"), "muted").pack(fill="x")
        for i, text in enumerate(self.cfg["phrases"]):
            row = tk.Frame(self.phrase_list, bg=ui.TAG_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=text, bg=ui.TAG_BG, fg=ui.INK, font=ui.F("small"), anchor="w", justify="left",
                     wraplength=300).pack(side="left", padx=10, pady=5, fill="x", expand=True)
            x = tk.Label(row, text="✕", bg=ui.TAG_BG, fg=ui.MUTED, cursor="hand2", padx=8)
            x.pack(side="right")
            x.bind("<Button-1>", lambda e, idx=i: self._del_phrase(idx))

    # ---- ajustes del dispositivo
    def _load_device(self):
        url = esp_client.url_of(self.cfg)

        def done(ok, cfg):
            if not (ok and cfg) or not self._alive():
                return
            for key, var in self.dev_vars.items():
                if key in cfg:
                    var.set(str(cfg[key]))
            self.auto_wifi.set(bool(cfg.get("autoWiFi")))
        run_async(self.top, lambda: esp_client.get_device_config(url), done)

    def _save_device(self):
        values = {k: v.get() for k, v in self.dev_vars.items() if str(v.get()).strip()}
        if self.cfg.get("connection_mode") != "local":
            values["autoWiFi"] = "1" if self.auto_wifi.get() else "0"
        url = esp_client.url_of(self.cfg)

        def done(ok, res):
            if ok and res:
                self.dev_notice.set(t("configGuardadaAlert"), "success")
                self._load_device()
                if hasattr(self, "dur_vars"):
                    self._load_durations()
            else:
                self.dev_notice.set(t("errorEsp"), "error")
        run_async(self.top, lambda: esp_client.save_device_config(url, values), done)
