"""Ventana "Sesiones sugeridas": muestra sesiones de trabajo recomendadas según
tu calendario (suscrito por enlace o subido como .ics) y los controles/entregas
que agregues a mano. Estilo compartido con la extensión y la página del ESP-01S.
"""
import os
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import filedialog

import calendar_planner as cp
import calendar_sync
import esp_client
import manual_events as me
import ui
from config import calendar_path, load_config, save_config

_window = {"toplevel": None}

KIND_LABEL = {"exam": "Evaluación", "deadline": "Entrega", "review": "Repaso"}
# (color del acento y del texto, fondo de la pill)
def kind_colors():
    return {
        "exam": (ui.DANGER, ui.DANGER_BG),
        "deadline": (ui.ACCENT, ui.GHOST_BG),
        "review": (ui.SUCCESS_FG, ui.SUCCESS_BG),
    }

LINK_HELP = (
    "Cómo obtener el enlace\n"
    "• Google Calendar: ⋮ junto al calendario → Configuración y uso compartido → "
    "«Dirección secreta en formato iCal».\n"
    "• Outlook: Configuración → Calendario → Calendarios compartidos → "
    "«Publicar un calendario» → enlace ICS.\n\n"
    "Privacidad: el enlace funciona como una contraseña, quien lo tenga puede ver tu "
    "calendario (en Google puedes restablecerlo). Se guarda solo en este computador. "
    "Google y Outlook pueden tardar horas en reflejar un cambio nuevo, y en cuentas "
    "institucionales el administrador puede haber desactivado esta opción."
)


def _read_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _run_async(widget, func, callback):
    """Ejecuta `func` en un hilo y entrega el resultado a `callback` en el hilo de la interfaz."""
    box = {}

    def work():
        try:
            box["r"] = ("ok", func())
        except Exception as exc:  # nunca dejar la interfaz esperando
            box["r"] = ("error", exc)

    threading.Thread(target=work, daemon=True).start()

    def poll():
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        if "r" not in box:
            widget.after(100, poll)
            return
        callback(*box["r"])

    poll()


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


# ---------------------------------------------------------------------------
# Lista de sesiones (tarjetas con acento de color por tipo)
# ---------------------------------------------------------------------------
class SessionList(tk.Frame):
    def __init__(self, parent, on_activate):
        super().__init__(parent, bg=ui.SURFACE)
        self._on_activate = on_activate
        self.canvas = tk.Canvas(self, bg=ui.SURFACE, highlightthickness=0, bd=0)
        self._sb = ui.scrollbar(self, self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=ui.SURFACE)
        self._win = self.canvas.create_window(0, 0, anchor="nw", window=self.inner)
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas)
        self._gone = False
        self.bind("<Destroy>", lambda e: setattr(self, "_gone", True) if e.widget is self else None)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(ev, self._wheel, add="+")
        ui.enable_touch_scroll(self, self.canvas, lambda: self.inner.winfo_reqheight() > self.canvas.winfo_height())
        self._rows = {}
        self._wrapped = []
        self.selected = None

    # -- desplazamiento -------------------------------------------------------
    def _on_scroll(self, first, last):
        self._sb.set(first, last)
        if float(first) <= 0.0 and float(last) >= 1.0:
            self._sb.pack_forget()
        elif not self._sb.winfo_ismapped():
            self._sb.pack(side="right", fill="y", padx=(4, 0))

    def _on_canvas(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)
        for lbl in self._wrapped:
            lbl.configure(wraplength=max(180, e.width - 330))

    def _wheel(self, e):
        if not ui.wheel_over(self, e) or self.inner.winfo_reqheight() <= self.canvas.winfo_height():
            return
        n = ui.wheel_units(self, e, 2)
        if n:
            self.canvas.yview_scroll(n, "units")

    # -- contenido -------------------------------------------------------------
    def clear(self):
        for child in self.inner.winfo_children():
            child.destroy()
        self._rows.clear()
        self._wrapped.clear()
        self.selected = None
        self.canvas.yview_moveto(0)

    def show_empty(self, title, body, actions=()):
        self.clear()
        box = tk.Frame(self.inner, bg=ui.SURFACE)
        box.pack(fill="x", pady=(46, 0))
        ui.label(box, title, kind="title", bg=ui.SURFACE).pack(anchor="center")
        lbl = ui.label(box, body, kind="muted", bg=ui.SURFACE, wraplength=460)
        lbl.configure(anchor="center", justify="center")
        lbl.pack(pady=(6, 14))
        row = tk.Frame(box, bg=ui.SURFACE)
        row.pack()
        for text, cmd, style in actions:
            ui.Button(row, text, cmd, style=style).pack(side="left", padx=4)

    def set_sessions(self, sessions, today):
        self.clear()
        current_day = None
        for s in sessions:
            d = s.start.date()
            if d != current_day:
                current_day = d
                label = f"{cp.DAYS_ES[d.weekday()]} {d.day:02d}/{d.month:02d}"
                if d == today:
                    label += " · hoy"
                ui.label(self.inner, label, kind="eyebrow", bg=ui.SURFACE).pack(
                    fill="x", pady=(10 if self._rows else 0, 6), padx=2)
            self._add_row(s)

    def _add_row(self, s):
        accent, tint = kind_colors()[s.kind]
        key = session_key(s)
        row = tk.Frame(self.inner, bg=ui.SURFACE, highlightthickness=1, highlightbackground=ui.LINE,
                       bd=0, cursor="hand2")
        row.pack(fill="x", pady=(0, 8), padx=1)
        tk.Frame(row, bg=accent, width=4).pack(side="left", fill="y")
        when = tk.Frame(row, bg=ui.SURFACE)
        when.pack(side="left", padx=(14, 12), pady=10)
        tk.Label(when, text=f"{s.start:%H:%M}", font=ui.F("time"), fg=ui.INK, bg=ui.SURFACE).pack(anchor="w")
        tk.Label(when, text=f"{s.end:%H:%M}", font=ui.F("small"), fg=ui.MUTED, bg=ui.SURFACE).pack(anchor="w")
        pills = tk.Frame(row, bg=ui.SURFACE)
        pills.pack(side="right", padx=14)
        ui.Pill(pills, KIND_LABEL[s.kind], accent, tint).pack(side="top", anchor="e")
        ui.Pill(pills, f"{s.minutes} min", ui.MUTED, ui.TAG_BG).pack(side="top", anchor="e", pady=(6, 0))
        if key in planned_keys():
            ui.Pill(pills, "✓ En mi agenda", ui.SUCCESS_FG, ui.SUCCESS_BG).pack(side="top", anchor="e", pady=(6, 0))
        mid = tk.Frame(row, bg=ui.SURFACE)
        mid.pack(side="left", fill="x", expand=True, pady=10)
        tk.Label(mid, text=s.title, font=ui.F("bold"), fg=ui.INK, bg=ui.SURFACE, anchor="w",
                 justify="left").pack(fill="x")
        reason = tk.Label(mid, text=s.reason, font=ui.F("small"), fg=ui.MUTED, bg=ui.SURFACE,
                          anchor="w", justify="left", wraplength=420)
        reason.pack(fill="x", pady=(2, 0))
        self._wrapped.append(reason)
        self._rows[key] = (row, s)

        for w in _walk(row):
            w.bind("<Button-1>", lambda e, k=key: self.select(k), add="+")
            w.bind("<Double-Button-1>", lambda e, k=key: (self.select(k), self._on_activate()), add="+")
            w.bind("<Enter>", lambda e, k=key: self._hover(k, True), add="+")
            w.bind("<Leave>", lambda e, k=key: self._hover(k, False), add="+")

    def _paint(self, key):
        row, _s = self._rows[key]
        if key == self.selected:
            row.configure(highlightbackground=ui.PRIMARY, highlightthickness=2)
        else:
            row.configure(highlightbackground=ui.LINE, highlightthickness=1)

    def _hover(self, key, on):
        if key in self._rows and key != self.selected:
            row, _s = self._rows[key]
            row.configure(highlightbackground=ui.mix(ui.LINE, ui.PRIMARY, 0.55) if on else ui.LINE)

    def select(self, key):
        prev = self.selected
        self.selected = key
        if prev in self._rows:
            self._paint(prev)
        if key in self._rows:
            self._paint(key)

    @property
    def selected_session(self):
        item = self._rows.get(self.selected)
        return item[1] if item else None


# ---------------------------------------------------------------------------
# Diálogo: origen del calendario
# ---------------------------------------------------------------------------
def session_key(s):
    return f"{s.start:%Y%m%d%H%M}|{s.title}"


def planned_keys():
    """Claves de las sesiones sugeridas que el usuario ya agregó a su agenda."""
    return {p.get("id") for p in load_config().get("planned_sessions", [])}


def toggle_planned(s):
    """Agrega la sesión a la agenda (o la quita si ya estaba). Devuelve True si quedó agregada."""
    cfg = load_config()
    key = session_key(s)
    items = [p for p in cfg.get("planned_sessions", []) if p.get("id") != key]
    added = len(items) == len(cfg.get("planned_sessions", []))
    if added:
        items.append({"id": key, "start": s.start.strftime("%Y-%m-%dT%H:%M"), "minutes": int(s.minutes),
                      "title": s.title, "kind": s.kind, "subject": s.subject})
    cutoff = datetime.now() - timedelta(days=3)
    items = [p for p in items if _planned_start(p) is None or _planned_start(p) > cutoff]
    cfg["planned_sessions"] = items
    save_config(cfg)
    return added


def _planned_start(p):
    try:
        return datetime.strptime(p["start"], "%Y-%m-%dT%H:%M")
    except (KeyError, ValueError, TypeError):
        return None


def _open_source_dialog(parent, on_change):
    top, _hero, body = ui.make_window(
        parent, "Calendario", "660x760", "Calendario", minsize=(600, 620),
        eyebrow="ORIGEN DE LOS EVENTOS", hero_h=72, modal=True)
    cfg = load_config()

    # --- Suscripción por enlace -------------------------------------------------
    link = ui.Card(body)
    link.pack(fill="x", pady=(0, 12))
    head = tk.Frame(link.body, bg=ui.SURFACE)
    head.pack(fill="x")
    ui.label(head, "Suscripción por enlace", kind="title", bg=ui.SURFACE).pack(side="left")
    ui.Pill(head, "Recomendado", ui.SUCCESS_FG, ui.SUCCESS_BG).pack(side="right")
    ui.label(link.body, "Pega el enlace una vez y se actualiza solo mientras la app esté abierta.",
             kind="muted", bg=ui.SURFACE).pack(fill="x", pady=(4, 8))

    url_var = tk.StringVar(value=cfg.get("calendar_url", ""))
    entry = ui.entry(link.body, url_var, show="•")
    entry.pack(fill="x")
    show_var = tk.BooleanVar(value=False)
    ui.checkbutton(link.body, "Mostrar enlace", show_var,
                   command=lambda: entry.configure(show="" if show_var.get() else "•")).pack(anchor="w", pady=(6, 0))

    every = tk.Frame(link.body, bg=ui.SURFACE)
    every.pack(fill="x", pady=(8, 10))
    ui.label(every, "Actualizar cada", kind="muted", bg=ui.SURFACE).pack(side="left")
    every_var = tk.IntVar(value=int(cfg.get("calendar_refresh_minutes", 60)))
    ui.spinbox(every, every_var, 15, 1440, width=6, increment=15).pack(side="left", padx=8)
    ui.label(every, "minutos", kind="muted", bg=ui.SURFACE).pack(side="left")

    notice = ui.Notice(link.body, "info")

    def status_text():
        st = calendar_sync.status()
        if st["last_error"]:
            return "Última actualización fallida: " + st["last_error"], "error"
        if st["last_ok"]:
            return f"Última actualización correcta a las {datetime.fromtimestamp(st['last_ok']):%H:%M}.", "success"
        if load_config().get("calendar_url"):
            return "Suscrito. Esperando la primera actualización…", "info"
        return "", "info"

    buttons = []

    def set_busy(busy):
        for b in buttons:
            b.configure(state="disabled" if busy else "normal")

    def save_and_sync():
        url = url_var.get().strip()
        if not url:
            notice.set("Pega primero el enlace de tu calendario.", "error")
            return
        try:
            minutes = max(15, min(1440, int(every_var.get())))
        except (tk.TclError, ValueError):
            minutes = 60
        notice.set("Descargando calendario…", "info")
        set_busy(True)

        def done(kind, result):
            set_busy(False)
            if kind == "error":
                notice.set("Error inesperado al actualizar.", "error")
                return
            ok, text, _changed = result
            if not ok:
                notice.set(text + " (No se guardó el enlace.)", "error")
                return
            c = load_config()
            c.update(calendar_url=url, calendar_refresh_minutes=minutes, calendar_name="Suscripción por enlace")
            save_config(c)
            notice.set(f"Listo: suscrito. Se actualizará cada {minutes} min mientras la app esté abierta.", "success")
            on_change()

        _run_async(top, lambda: calendar_sync.sync_now(url), done)

    def stop_sync():
        c = load_config()
        if not c.get("calendar_url"):
            notice.set("No hay ninguna suscripción activa.", "info")
            return
        c["calendar_url"] = ""
        c["calendar_name"] = "calendar.ics (última copia)"
        save_config(c)
        url_var.set("")
        notice.set("Suscripción detenida. Se conserva la última copia descargada.", "info")
        on_change()

    row = tk.Frame(link.body, bg=ui.SURFACE)
    row.pack(fill="x")
    b1 = ui.Button(row, "Guardar y actualizar", save_and_sync)
    b2 = ui.Button(row, "Dejar de sincronizar", stop_sync, style="ghost")
    b1.pack(side="left")
    b2.pack(side="left", padx=8)
    buttons += [b1, b2]
    notice.pack(fill="x", pady=(10, 0))
    first_text, first_kind = status_text()
    if first_text:
        notice.set(first_text, first_kind)

    # --- Archivo ----------------------------------------------------------------
    filec = ui.Card(body)
    filec.pack(fill="x", pady=(0, 12))
    ui.label(filec.body, "Archivo .ics", kind="title", bg=ui.SURFACE).pack(fill="x")
    ui.label(filec.body, "Alternativa manual: exporta tu calendario y súbelo. Reemplaza la suscripción.",
             kind="muted", bg=ui.SURFACE).pack(fill="x", pady=(4, 10))

    def upload():
        if load_config().get("calendar_url") and not ui.confirm(
            top, "Reemplazar suscripción",
            "Tienes una suscripción por enlace. Subir un archivo la reemplaza y deja de sincronizar."):
            return
        path = filedialog.askopenfilename(
            parent=top, title="Elige tu calendario",
            filetypes=[("Calendario iCalendar", "*.ics"), ("Todos los archivos", "*.*")])
        if not path:
            return
        try:
            text = _read_text(path)
        except OSError as exc:
            notice.set(f"No se pudo abrir el archivo: {exc}", "error")
            return
        if "BEGIN:VCALENDAR" not in text.upper():
            notice.set("Ese archivo no parece un calendario .ics válido.", "error")
            return
        tmp = calendar_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, calendar_path())          # atómico: un corte a mitad de escritura no deja el calendario roto
        c = load_config()
        c.update(calendar_name=os.path.basename(path), calendar_url="")
        save_config(c)
        url_var.set("")
        notice.set(f"Archivo cargado: {os.path.basename(path)}.", "success")
        on_change()

    def remove():
        if not os.path.exists(calendar_path()) and not load_config().get("calendar_url"):
            notice.set("No hay calendario guardado.", "info")
            return
        if ui.confirm(top, "Quitar calendario", "Se borrará el calendario y la suscripción de este equipo.",
                      yes="Quitar", danger=True):
            try:
                os.remove(calendar_path())
            except OSError:
                pass
            c = load_config()
            c.update(calendar_name="", calendar_url="")
            save_config(c)
            url_var.set("")
            notice.set("Calendario quitado.", "info")
            on_change()

    frow = tk.Frame(filec.body, bg=ui.SURFACE)
    frow.pack(fill="x")
    ui.Button(frow, "Subir archivo…", upload, style="ghost").pack(side="left")
    ui.Button(frow, "Quitar calendario", remove, style="danger").pack(side="left", padx=8)

    # --- Ayuda ---------------------------------------------------------------------
    help_card = ui.Card(body, fill=ui.SOFT, radius=14)
    help_card.pack(fill="x")
    tk.Label(help_card.body, text=LINK_HELP, bg=ui.SOFT, fg=ui.MUTED, font=ui.F("small"), anchor="w",
             justify="left", wraplength=560).pack(fill="x")


# ---------------------------------------------------------------------------
# Diálogo: eventos manuales
# ---------------------------------------------------------------------------
def _open_manual_dialog(parent, on_change):
    top, _hero, body = ui.make_window(
        parent, "Eventos manuales", "640x720", "Eventos manuales", minsize=(560, 640),
        eyebrow="CONTROLES, ENTREGAS Y CLASES", hero_h=72, modal=True)

    # Quita lo que terminó hace más de una semana.
    c = load_config()
    items = me.purge_old(c.get("manual_events", []))
    if len(items) != len(c.get("manual_events", [])):
        c["manual_events"] = items
        save_config(c)

    form = ui.Card(body)
    form.pack(fill="x", pady=(0, 12))
    ui.label(form.body, "Agregar evento", kind="title", bg=ui.SURFACE).pack(fill="x", pady=(0, 8))
    grid = tk.Frame(form.body, bg=ui.SURFACE)
    grid.pack(fill="x")
    grid.columnconfigure(1, weight=1)

    title_var = tk.StringVar()
    kind_var = tk.StringVar(value=me.KINDS["exam"][0])
    date_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
    time_var = tk.StringVar(value="10:00")
    mins_var = tk.IntVar(value=me.KINDS["exam"][2])

    def row(r, text, widget):
        ui.label(grid, text, kind="muted", bg=ui.SURFACE).grid(row=r, column=0, sticky="w", pady=4, padx=(0, 14))
        widget.grid(row=r, column=1, sticky="we", pady=4)

    row(0, "Título", ui.entry(grid, title_var))
    kind_box = ui.combobox(grid, kind_var, [me.KINDS[k][0] for k in me.KIND_ORDER])
    row(1, "Tipo", kind_box)
    row(2, "Fecha (dd/mm/aaaa)", ui.entry(grid, date_var, width=14))
    row(3, "Hora (HH:MM)", ui.entry(grid, time_var, width=8))
    row(4, "Duración (min)", ui.spinbox(grid, mins_var, 0, 600, width=6, increment=15))

    def kind_key():
        label = kind_var.get()
        for k in me.KIND_ORDER:
            if me.KINDS[k][0] == label:
                return k
        return "other"

    kind_box.bind("<<ComboboxSelected>>", lambda _e: mins_var.set(me.KINDS[kind_key()][2]))

    notice = ui.Notice(form.body, "error")
    notice.pack(fill="x", pady=(8, 0))

    lst = ui.Card(body, expand=True)
    lst.pack(fill="both", expand=True)
    ui.label(lst.body, "Tus eventos manuales", kind="title", bg=ui.SURFACE).pack(fill="x", pady=(0, 8))
    bottom = tk.Frame(lst.body, bg=ui.SURFACE)
    bottom.pack(side="bottom", fill="x", pady=(10, 0))
    sl = ui.ScrollList(lst.body, height=5, selectmode="browse")
    sl.pack(fill="both", expand=True)
    listbox = sl.listbox
    ids = []

    def reload_list():
        listbox.delete(0, "end")
        ids.clear()
        for it in me.purge_old(load_config().get("manual_events", []), keep_days=3650):
            listbox.insert("end", me.describe(it))
            ids.append(it["id"])

    def add():
        try:
            it = me.make_item(title_var.get(), kind_key(), date_var.get(), time_var.get(), mins_var.get())
        except (ValueError, tk.TclError) as exc:
            notice.set(str(exc), "error")
            return
        notice.set("")
        cfg2 = load_config()
        cfg2["manual_events"] = me.purge_old(cfg2.get("manual_events", []) + [it], keep_days=3650)
        save_config(cfg2)
        title_var.set("")
        reload_list()
        on_change()

    def delete():
        sel = listbox.curselection()
        if not sel:
            return
        target = ids[sel[0]]
        cfg2 = load_config()
        cfg2["manual_events"] = [i for i in cfg2.get("manual_events", []) if i.get("id") != target]
        save_config(cfg2)
        reload_list()
        on_change()

    arow = tk.Frame(form.body, bg=ui.SURFACE)
    arow.pack(fill="x", pady=(10, 0))
    ui.Button(arow, "Agregar", add).pack(side="right")
    ui.Button(bottom, "Eliminar seleccionado", delete, style="danger").pack(side="left")
    reload_list()


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------
def open_calendar_window(root):
    existing = _window["toplevel"]
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_force()
        return
    ui.refresh_theme()

    win, hero, content = ui.make_window(
        root, "Focus Relay Desktop · Sesiones sugeridas", "920x720", "Sesiones sugeridas",
        minsize=(800, 600))
    _window["toplevel"] = win
    cfg = load_config()

    # --- Pie fijo ----------------------------------------------------------------
    footer = tk.Frame(win, bg=ui.CANVAS)
    footer.pack(side="bottom", fill="x", padx=18, pady=(0, 16))
    notice = ui.Notice(footer, "info")
    notice.pack(fill="x", pady=(0, 10))
    actions = tk.Frame(footer, bg=ui.CANVAS)
    actions.pack(fill="x")
    content.pack_forget()
    content.pack(fill="both", expand=True, padx=18, pady=(16, 10))

    # --- Ajustes -------------------------------------------------------------------
    opts = ui.Card(content, pad=12, radius=14)
    opts.pack(fill="x", pady=(0, 12))
    orow = tk.Frame(opts.body, bg=ui.SURFACE)
    orow.pack(fill="x")

    def spin(label, value, lo, hi):
        ui.label(orow, label, kind="muted", bg=ui.SURFACE).pack(side="left")
        var = tk.IntVar(value=int(value))
        ui.spinbox(orow, var, lo, hi, width=4).pack(side="left", padx=(6, 16))
        return var

    horizon_var = spin("Días", cfg.get("horizon_days", 7), 1, 14)
    start_var = spin("Estudio desde las", cfg.get("day_start", 8), 5, 20)
    end_var = spin("hasta las", cfg.get("day_end", 22), 8, 24)
    max_var = spin("Máx. sesiones por día", cfg.get("max_sessions_per_day", 4), 1, 8)

    # --- Lista ----------------------------------------------------------------------
    card = ui.Card(content, expand=True)
    card.pack(fill="both", expand=True)
    head = tk.Frame(card.body, bg=ui.SURFACE)
    head.pack(fill="x", pady=(0, 10))
    ui.label(head, "Próximas sesiones", kind="title", bg=ui.SURFACE).pack(side="left")
    count_holder = tk.Frame(head, bg=ui.SURFACE)
    count_holder.pack(side="right")
    summary_var = tk.StringVar(value="")
    tk.Label(head, textvariable=summary_var, bg=ui.SURFACE, fg=ui.MUTED, font=ui.F("small")).pack(
        side="right", padx=(0, 10))

    def set_notice(text, kind="info"):
        notice.set(text, kind)

    def start_selected(_event=None):
        s = slist.selected_session
        if s is None:
            set_notice("Elige una sesión de la lista para iniciarla en el ESP-01S.", "info")
            return
        esp_url = esp_client.url_of(load_config())
        set_notice("Contactando al ESP-01S…", "info")

        def done(kind, result):
            if kind == "error":
                set_notice("No se pudo iniciar la sesión.", "error")
                return
            status, msg = result
            if status == "ok":
                set_notice(msg + f" «{s.subject}» quedará registrada en tu historial; el bloqueo se activa solo.",
                           "success")
            else:
                set_notice(msg, "error")

        _run_async(win, lambda: esp_client.start_session(esp_url, s.minutes, s.subject), done)

    slist = SessionList(card.body, start_selected)
    slist.pack(fill="both", expand=True)

    # --- Lógica --------------------------------------------------------------------
    def planner_config():
        s, e = int(start_var.get()), int(end_var.get())
        if e <= s:
            e = min(24, s + 1)
        pc = cp.PlannerConfig(day_start=s, day_end=e, horizon_days=int(horizon_var.get()),
                              max_sessions_per_day=int(max_var.get()))
        try:                                        # adaptación a mi uso: duración habitual y mejores horas
            import adaptive
            prof = adaptive.load_profile()
            mins = adaptive.recommended_minutes(prof) if prof else None
            if mins:
                pc.focus_minutes, pc.adapted = mins, True
            pc.hour_scores = adaptive.hour_scores(prof) if prof else {}
        except Exception:
            pass
        return pc

    def open_source():
        _open_source_dialog(win, refresh)

    def open_manual():
        _open_manual_dialog(win, refresh)

    def set_count(n):
        for w in count_holder.winfo_children():
            w.destroy()
        if n:
            ui.Pill(count_holder, f"{n} sesión" + ("es" if n != 1 else ""), ui.ACCENT, ui.GHOST_BG).pack()

    def hero_state(c, has_file):
        if c.get("calendar_url"):
            st = calendar_sync.status()
            if st["last_error"]:
                return "Suscripción · error al actualizar", False
            if st["last_ok"]:
                return f"Suscripción · actualizada {datetime.fromtimestamp(st['last_ok']):%H:%M}", True
            return "Suscripción · esperando actualización", False
        if has_file:
            return (c.get("calendar_name") or "calendar.ics"), True
        return "Sin calendario", False

    def refresh():
        c = load_config()
        manual = me.to_events(c.get("manual_events", []))
        has_file = os.path.exists(calendar_path())
        text, online = hero_state(c, has_file)
        hero.set_status(text, online)
        if not has_file and not manual:
            set_count(0)
            summary_var.set("")
            slist.show_empty(
                "Aún no hay calendario ni eventos",
                "Conecta tu calendario con un enlace (se actualiza solo) o sube un archivo .ics. "
                "También puedes anotar a mano controles y entregas.",
                actions=[("Conectar calendario", open_source, "primary"),
                         ("Agregar evento manual", open_manual, "ghost")])
            return
        pc = planner_config()
        now = datetime.now()
        try:
            events = []
            if has_file:
                events = cp.load_events(_read_text(calendar_path()), now - timedelta(days=1),
                                        now + timedelta(days=pc.horizon_days + 9))
            events = sorted(events + [e for e in manual if e.end > now - timedelta(days=1)],
                            key=lambda e: (e.start, e.summary))
            sugg = cp.recommend(events, now, pc)
        except Exception as exc:
            set_count(0)
            summary_var.set("")
            slist.show_empty("No se pudo leer el calendario", f"{exc}")
            return

        upcoming = [e for e in events if e.end > now]
        n_manual = len([e for e in manual if e.end > now])
        summary_var.set(f"{len(upcoming)} eventos próximos" + (f" · {n_manual} manual" + ("es" if n_manual != 1 else "")
                                                               if n_manual else ""))
        set_count(len(sugg))
        if not sugg:
            slist.show_empty(
                "Sin sesiones para recomendar",
                "No hay evaluaciones, entregas o clases próximas, o no quedan huecos libres dentro de "
                "tu horario de estudio. Prueba ampliar los días o el horario.")
            return
        slist.set_sessions(sugg, now.date())

    def recalc():
        c = load_config()
        pc = planner_config()
        c.update(day_start=pc.day_start, day_end=pc.day_end, horizon_days=pc.horizon_days,
                 max_sessions_per_day=pc.max_sessions_per_day)
        save_config(c)
        refresh()

    ui.Button(orow, "Recalcular", recalc, style="ghost", padx=14, pady=6).pack(side="right")

    ui.Button(actions, "Calendario…", open_source, style="ghost").pack(side="left")
    ui.Button(actions, "Eventos manuales…", open_manual, style="ghost").pack(side="left", padx=8)
    ui.Button(actions, "Iniciar en el ESP", start_selected).pack(side="right")

    def add_to_agenda():
        s = slist.selected_session
        if s is None:
            set_notice("Elige primero una sesión de la lista.", "info")
            return
        key = session_key(s)
        added = toggle_planned(s)
        refresh()
        slist.select(key)
        set_notice(("Agregada a tu agenda: " if added else "Quitada de tu agenda: ") + s.title, "success")

    ui.Button(actions, "Agregar a mi agenda", add_to_agenda, style="ghost").pack(side="right", padx=(0, 8))

    # Refresco automático: si la suscripción trae cambios, la lista se actualiza sola.
    last_seen = {"sig": None}

    def signature():
        try:
            mtime = os.path.getmtime(calendar_path())
        except OSError:
            mtime = 0
        st = calendar_sync.status()
        return (mtime, st["last_ok"], st["last_error"])

    def watch():
        try:
            if not win.winfo_exists():
                return
        except tk.TclError:
            return
        sig = signature()
        if sig != last_seen["sig"]:
            if last_seen["sig"] is not None:
                refresh()
            last_seen["sig"] = sig
        win.after(5000, watch)

    def on_close():
        _window["toplevel"] = None
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)
    refresh()
    last_seen["sig"] = signature()
    win.after(5000, watch)
