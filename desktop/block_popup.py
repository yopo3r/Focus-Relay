"""Ventanita de aviso cuando se bloquea una aplicación (en vez de una notificación del sistema).

`show()` se puede llamar desde cualquier hilo (el del bloqueo): solo encola. `pump(root)` corre en el hilo de la
interfaz, crea la ventana (siempre al frente, abajo a la derecha) y la cierra sola a los pocos segundos.
"""
import queue
import time
import tkinter as tk

import ui
from i18n import t

_q = queue.Queue()
_last = {}            # (nombre, tipo) -> hora del último aviso, para no apilar avisos iguales
_open = []            # ventanas abiertas
AUTO_CLOSE_MS = 7000
MAX_OPEN = 3


def show(name, kind, grace=0):
    """kind: «warn» (se cerrará en `grace` s) o «closed» (ya se cerró)."""
    key = (name, kind)
    now = time.time()
    if now - _last.get(key, 0) < 8:
        return
    _last[key] = now
    _q.put((name, kind, int(grace)))


def message(name, kind, grace):
    if kind == "warn":
        return t("bloqPopupCierra", name=name, s=grace)
    return t("bloqPopupCerrada", name=name)


def _place(top):
    top.update_idletasks()
    w, h = top.winfo_reqwidth(), top.winfo_reqheight()
    x = top.winfo_screenwidth() - w - 24
    y = top.winfo_screenheight() - h - 70 - 10 * len(_open) - sum(o.winfo_reqheight() + 8 for o in _open if o.winfo_exists())
    top.geometry(f"+{max(0, x)}+{max(0, y)}")


def _popup(root, name, kind, grace):
    for w in list(_open):
        if not w.winfo_exists():
            _open.remove(w)
    if len(_open) >= MAX_OPEN:
        return
    top = tk.Toplevel(root)
    top.title(t("bloqPopupTitulo"))
    top.configure(bg=ui.SURFACE, highlightthickness=1, highlightbackground=ui.DANGER)
    try:
        top.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        ui.set_window_icon(top)
    except Exception:
        pass
    top.resizable(False, False)
    body = tk.Frame(top, bg=ui.SURFACE)
    body.pack(fill="both", expand=True, padx=18, pady=14)
    ui.label(body, "⛔ " + t("bloqPopupTitulo"), kind="title", bg=ui.SURFACE).pack(fill="x")
    ui.label(body, message(name, kind, grace), bg=ui.SURFACE, wraplength=300).pack(fill="x", pady=(6, 10))
    ui.Button(body, t("bloqPopupOk"), top.destroy, style="ghost").pack(anchor="e")
    _place(top)
    _open.append(top)
    top.after(AUTO_CLOSE_MS, lambda: top.winfo_exists() and top.destroy())


def pump(root, every_ms=300):
    """Atiende la cola desde el hilo de la interfaz; se reprograma sola."""
    try:
        while True:
            name, kind, grace = _q.get_nowait()
            try:
                _popup(root, name, kind, grace)
            except Exception as exc:
                print(f"[Focus Relay] aviso de bloqueo: {exc}")
    except queue.Empty:
        pass
    try:
        root.after(every_ms, lambda: pump(root, every_ms))
    except tk.TclError:
        pass
