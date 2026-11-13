"""Ventana de configuración de Focus Relay Desktop.

Mismo lenguaje visual que la extensión del navegador y la página del
ESP-01S (ver ui.py): tarjetas blancas sobre fondo azulado, encabezado en
degradado índigo y botones redondeados.
"""
import time
import tkinter as tk
from tkinter import ttk

import ui
from blocker import list_running_processes
from config import load_config, save_config

# (título, descripción) por modo de bloqueo
MODES = {
    "strict": ("Estricto", "Cierra la app apenas se detecta."),
    "warn": ("Con aviso previo", "Avisa y cierra tras unos segundos de gracia."),
    "prevent_launch": ("Solo prevenir apertura", "No toca lo que ya estaba abierto."),
}
MODE_ORDER = ["strict", "warn", "prevent_launch"]

_window_open = {"toplevel": None}


def open_config_window(root, shared_state, state_lock):
    """Abre (o trae al frente) la única ventana de configuración."""
    existing = _window_open["toplevel"]
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_force()
        return

    ui.refresh_theme()
    cfg = load_config()
    win, hero, content = ui.make_window(
        root, "Focus Relay Desktop · Configuración", "860x700", "Configuración", minsize=(780, 640)
    )
    _window_open["toplevel"] = win

    # --- Pie fijo: aviso + acciones ------------------------------------------
    footer = tk.Frame(win, bg=ui.CANVAS)
    footer.pack(side="bottom", fill="x", padx=18, pady=(0, 16))
    notice = ui.Notice(footer, "success")
    notice.pack(fill="x", pady=(0, 10))
    actions = tk.Frame(footer, bg=ui.CANVAS)
    actions.pack(fill="x")

    content.pack_forget()
    content.pack(fill="both", expand=True, padx=18, pady=(16, 10))
    content.columnconfigure(0, weight=1, uniform="col")
    content.columnconfigure(1, weight=1, uniform="col")
    content.rowconfigure(0, weight=1)

    left = tk.Frame(content, bg=ui.CANVAS)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))

    # --- Tarjeta: dispositivo -------------------------------------------------
    dev = ui.Card(left)
    dev.pack(fill="x", pady=(0, 14))
    local = cfg.get("connection_mode") == "local"
    esp_url_var = tk.StringVar(value=cfg.get("esp_url", ""))
    if not local:                                   # sin dispositivo no hay dirección que configurar
        ui.label(dev.body, "Dirección del ESP-01S", kind="title", bg=ui.SURFACE).pack(fill="x", pady=(0, 6))
        ui.entry(dev.body, esp_url_var).pack(fill="x")
        ui.label(dev.body, "Usa la IP que muestra el OLED, sin agregar /estado.", kind="muted",
                 bg=ui.SURFACE).pack(fill="x", pady=(4, 10))
    else:
        ui.label(dev.body, "Bloqueo de apps", kind="title", bg=ui.SURFACE).pack(fill="x", pady=(0, 6))
    enabled_var = tk.BooleanVar(value=cfg.get("enabled", True))
    ui.checkbutton(dev.body, "Activar bloqueo durante las sesiones",
                   enabled_var).pack(fill="x")
    timer_var = tk.BooleanVar(value=cfg.get("block_in_timer", True))
    if local:
        ui.checkbutton(dev.body, "Bloquear también en el Temporizador", timer_var).pack(fill="x", pady=(6, 0))

    # --- Tarjeta: intensidad --------------------------------------------------
    mode_card = ui.Card(left)
    mode_card.pack(fill="x")
    ui.label(mode_card.body, "Intensidad del bloqueo", kind="title", bg=ui.SURFACE).pack(fill="x", pady=(0, 8))
    mode_var = tk.StringVar(value=cfg.get("mode", "warn"))
    tiles = {}

    def paint_tiles(*_):
        for key, tile in tiles.items():
            sel = mode_var.get() == key
            tile.configure(highlightbackground=ui.PRIMARY if sel else ui.LINE,
                           highlightcolor=ui.PRIMARY, highlightthickness=2 if sel else 1)

    for key in MODE_ORDER:
        title, desc = MODES[key]
        tile = tk.Frame(mode_card.body, bg=ui.SURFACE, highlightthickness=1,
                        highlightbackground=ui.LINE, bd=0, cursor="hand2")
        tile.pack(fill="x", pady=(0, 6))
        tiles[key] = tile
        inner = tk.Frame(tile, bg=ui.SURFACE)
        inner.pack(fill="x", padx=10, pady=5)
        rb = ui.radiobutton(inner, "", mode_var, key, bg=ui.SURFACE)
        rb.pack(side="left", anchor="n")
        txt = tk.Frame(inner, bg=ui.SURFACE)
        txt.pack(side="left", fill="x", expand=True)
        t1 = ui.label(txt, title, kind="body", bg=ui.SURFACE)
        t1.configure(font=ui.F("bold"))
        t1.pack(fill="x")
        t2 = ui.label(txt, desc, kind="muted", bg=ui.SURFACE)
        t2.pack(fill="x")
        for w in (tile, inner, txt, t1, t2):
            w.bind("<Button-1>", lambda e, k=key: None if locked() else mode_var.set(k))
    mode_var.trace_add("write", paint_tiles)

    grace_row = tk.Frame(mode_card.body, bg=ui.SURFACE)
    grace_row.pack(fill="x", pady=(4, 0))
    ui.label(grace_row, "Segundos de gracia (con aviso previo)", kind="muted", bg=ui.SURFACE).pack(side="left")
    grace_var = tk.IntVar(value=int(cfg.get("grace_seconds", 10)))
    ui.spinbox(grace_row, grace_var, 3, 120, width=5).pack(side="right")
    win.after(30, paint_tiles)

    # --- Tarjeta: aplicaciones bloqueadas (ocupa la columna derecha) ---------
    apps = ui.Card(content, expand=True)
    apps.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
    ui.label(apps.body, "Aplicaciones bloqueadas", kind="title", bg=ui.SURFACE).pack(fill="x", pady=(0, 2))
    ui.label(apps.body, ("Solo se cierran durante el Pomodoro (y el Temporizador si lo activas)." if local else "Solo se cierran mientras hay una sesión activa en el ESP-01S."), kind="muted",
             bg=ui.SURFACE, wraplength=400).pack(fill="x", pady=(0, 10))

    btn_row = tk.Frame(apps.body, bg=ui.SURFACE)
    btn_row.pack(side="bottom", fill="x", pady=(12, 0))
    apps_list = ui.ScrollList(apps.body, height=8, selectmode="extended")
    apps_list.pack(fill="both", expand=True)
    apps_listbox = apps_list.listbox
    for app in cfg.get("blocked_apps", []):
        apps_listbox.insert("end", app)

    def add_from_running():
        if not refuse():
            _open_process_picker(win, apps_listbox)

    def add_manual():
        if refuse():
            return
        name = ui.ask_text(
            win, "Agregar aplicación",
            "Nombre del ejecutable (por ejemplo steam.exe en Windows, o steam en Linux):",
        )
        if name:
            apps_listbox.insert("end", name)

    def remove_selected():
        if refuse():
            return
        for idx in reversed(apps_listbox.curselection()):
            apps_listbox.delete(idx)

    ui.Button(btn_row, "+ De procesos activos", add_from_running, style="ghost").pack(side="left")
    ui.Button(btn_row, "+ Manual", add_manual, style="ghost").pack(side="left", padx=8)
    ui.Button(btn_row, "Quitar", remove_selected, style="danger").pack(side="left")

    # --- Bloqueo de la edición durante una sesión ----------------------------------
    LOCK_MSG = "Bloqueado mientras hay una sesión en marcha. Podrás editarlo al terminar."

    def locked():
        import guard
        with state_lock:
            return guard.block_settings_locked(shared_state.get("estado"), load_config())

    def refuse():
        """True (y avisa) si hay una sesión en marcha: no se toca nada."""
        if locked():
            notice.set(LOCK_MSG, "error")
            return True
        return False

    def widgets_of(root_w):
        for w in root_w.winfo_children():
            yield w
            yield from widgets_of(w)

    lock_state = {"on": None}

    def apply_lock(on):
        """Deshabilita (o rehabilita) los controles de edición mientras hay una sesión."""
        if lock_state["on"] == on:
            return
        lock_state["on"] = on
        for host in (left, apps.body, save_btn):
            for w in [host, *widgets_of(host)]:
                try:
                    if isinstance(w, ui.Button):
                        w.configure(state="disabled" if on else "normal")
                    elif isinstance(w, (ttk.Checkbutton, ttk.Radiobutton, ttk.Entry, ttk.Spinbox)):
                        w.state(["disabled"] if on else ["!disabled"])
                except (tk.TclError, AttributeError):
                    pass
        notice.set(LOCK_MSG, "error") if on else notice.set("", "success")

    # --- Acciones ----------------------------------------------------------------
    def do_save():
        if refuse():
            return
        new_cfg = load_config()
        try:
            grace = int(grace_var.get())
        except (tk.TclError, ValueError):
            grace = 10
        new_cfg.update(
            {
                "esp_url": esp_url_var.get().strip(),
                "enabled": bool(enabled_var.get()),
                "block_in_timer": bool(timer_var.get()),
                "mode": mode_var.get(),
                "grace_seconds": max(3, min(120, grace)),
                "blocked_apps": list(apps_listbox.get(0, "end")),
            }
        )
        save_config(new_cfg)
        notice.set("Guardado. Los cambios aplican en el próximo ciclo de revisión.", "success")

    def open_calendar():
        from calendar_gui import open_calendar_window  # import tardío: evita ciclo
        open_calendar_window(root)

    ui.Button(actions, "Calendario y sesiones sugeridas…", open_calendar, style="ghost").pack(side="left")
    save_btn = ui.Button(actions, "Guardar", do_save)
    save_btn.pack(side="right")

    # --- Estado en vivo -----------------------------------------------------------
    def refresh_status():
        if not win.winfo_exists():
            return
        apply_lock(locked())
        with state_lock:
            connected = shared_state.get("connected", False)
            block_active = shared_state.get("block_active", False)
            paused = time.time() < shared_state.get("suspend_until", 0.0)
        if not connected:
            hero.set_status("ESP-01S sin conexión", False)
        elif paused:
            hero.set_status("Bloqueo en pausa", True)
        elif block_active:
            hero.set_status("Sesión activa · bloqueando", True)
        else:
            hero.set_status("Conectado · en espera", True)
        win.after(1000, refresh_status)

    refresh_status()

    def on_close():
        _window_open["toplevel"] = None
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)


def _open_process_picker(parent, target_listbox):
    picker, _hero, body = ui.make_window(
        parent, "Procesos activos", "440x580", "Procesos activos", minsize=(380, 460),
        eyebrow="AGREGAR APLICACIONES", hero_h=72, modal=True,
    )
    card = ui.Card(body, expand=True)
    card.pack(fill="both", expand=True)

    ui.label(card.body, "Selecciona una o varias", kind="title", bg=ui.SURFACE).pack(fill="x")
    search_var = tk.StringVar()
    search = ui.entry(card.body, search_var)
    search.pack(fill="x", pady=(8, 10))
    search.focus_set()

    row = tk.Frame(card.body, bg=ui.SURFACE)
    row.pack(side="bottom", fill="x", pady=(12, 0))
    sl = ui.ScrollList(card.body, height=12, selectmode="extended")
    sl.pack(fill="both", expand=True)
    lb = sl.listbox

    all_procs = list_running_processes()

    def populate(filter_text=""):
        lb.delete(0, "end")
        filter_text = filter_text.lower()
        for name in all_procs:
            if filter_text in name.lower():
                lb.insert("end", name)

    populate()
    search_var.trace_add("write", lambda *a: populate(search_var.get()))

    def confirm():
        existing = set(target_listbox.get(0, "end"))
        for idx in lb.curselection():
            name = lb.get(idx)
            if name not in existing:
                target_listbox.insert("end", name)
                existing.add(name)
        picker.destroy()

    ui.Button(row, "Agregar selección", confirm).pack(side="right")
    ui.Button(row, "Cancelar", picker.destroy, style="ghost").pack(side="right", padx=(0, 8))
