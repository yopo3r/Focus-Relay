"""Pestaña "Acerca de": versión, autoría, carpeta de datos, declaración de privacidad y créditos."""
import os
import platform
import subprocess
import threading
import tkinter as tk
import webbrowser

import i18n
import ui
import updates
from config import APP_VERSION, config_dir, system_env
from i18n import t


def _wrapped(dash, parent, text, kind="body", **kw):
    """Etiqueta que ajusta su salto de línea al ancho disponible."""
    lbl = dash._lbl(parent, text, kind, **kw)
    lbl.pack(fill="x")
    parent.bind("<Configure>", lambda e: lbl.configure(wraplength=max(240, e.width - 6)), add="+")
    return lbl


def open_folder(path):
    """Abre la carpeta en el explorador del sistema. True si se pudo lanzar."""
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(path)                                   # noqa: S606 (solo Windows)
        elif system == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=system_env())
        return True
    except (OSError, AttributeError):
        return False


def build_github_card(self, parent):
    """Tarjeta con el repositorio: abrirlo, buscar versión nueva, reportar errores y proponer mejoras."""
    a = self._card(parent, t("acercaTitulo"), info=t("acercaInfo"))
    a.pack(fill="x", pady=(0, 14))
    row = tk.Frame(a.body, bg=ui.SURFACE)
    row.pack(fill="x", pady=(8, 0))
    ui.Button(row, t("acercaRepo"), lambda: webbrowser.open(updates.REPO_URL)).pack(side="left")
    ui.Button(row, t("acercaActualizar"), lambda: check(), style="ghost").pack(side="left", padx=8)
    row2 = tk.Frame(a.body, bg=ui.SURFACE)
    row2.pack(fill="x", pady=(8, 0))
    ui.Button(row2, t("acercaError"), lambda: webbrowser.open(updates.BUG_URL), style="ghost").pack(side="left")
    ui.Button(row2, t("acercaMejora"), lambda: webbrowser.open(updates.IDEA_URL), style="ghost").pack(side="left", padx=8)
    notice = ui.Notice(a.body, "success")
    notice.pack(fill="x", pady=(10, 0))

    def show(kind, text, url=None):
        try:
            notice.set(text, kind)
        except Exception:
            return
        if url:
            webbrowser.open(url)

    def check():
        notice.set(t("acercaBuscando"), "info")

        def work():
            try:
                latest = updates.fetch_latest()
            except (OSError, ValueError):
                self.top.after(0, lambda: show("error", t("acercaSinRed")))
                return
            if latest and updates.is_newer(latest[0], APP_VERSION):
                self.top.after(0, lambda: show("success", t("acercaNueva", v=latest[0]), latest[1]))
            else:
                self.top.after(0, lambda: show("success", t("acercaAlDia")))
        threading.Thread(target=work, daemon=True).start()


class AboutPage:
    def __init__(self, dash, parent):
        self.d = dash
        path = config_dir()
        # --- identidad
        card = dash._card(parent)
        card.pack(fill="x", pady=(0, 14))
        b = card.body
        dash._lbl(b, "Focus Relay Desktop", "title").pack(fill="x")
        dash._lbl(b, t("acercaVersion", v=APP_VERSION) + "  ·  " + t("acercaAutor"), "muted").pack(fill="x", pady=(2, 8))
        _wrapped(dash, b, t("acercaDescripcion"))
        ui.Button(b, t("tutVer"), dash.show_tutorial, style="ghost").pack(anchor="w", pady=(10, 0))

        # --- repositorio
        build_github_card(dash, parent)

        # --- datos locales
        card = dash._card(parent, t("acercaDatosTitulo"))
        card.pack(fill="x", pady=(0, 14))
        b = card.body
        dash._lbl(b, t("acercaCarpeta"), "muted").pack(fill="x")
        path_lbl = tk.Label(b, text=path, bg=ui.TAG_BG, fg=ui.INK, font=ui.F("small"), anchor="w", justify="left",
                            padx=10, pady=8)
        path_lbl.pack(fill="x", pady=(4, 8))
        b.bind("<Configure>", lambda e: path_lbl.configure(wraplength=max(240, e.width - 24)), add="+")
        row = tk.Frame(b, bg=ui.SURFACE)
        row.pack(fill="x")
        self.notice = ui.Notice(b, "success")
        ui.Button(row, t("acercaAbrirCarpeta"), lambda: self._open(path), style="ghost").pack(side="left")
        ui.Button(row, t("acercaCopiarRuta"), lambda: self._copy(path), style="ghost").pack(side="left", padx=8)
        self.notice.pack(fill="x", pady=(8, 0))

        # --- privacidad
        card = dash._card(parent, t("privTitulo"))
        card.pack(fill="x", pady=(0, 14))
        b = card.body
        summary = tk.Frame(b, bg=ui.GHOST_BG)
        summary.pack(fill="x", pady=(0, 10))
        tk.Frame(summary, bg=ui.PRIMARY, width=4).pack(side="left", fill="y")
        inner = tk.Frame(summary, bg=ui.GHOST_BG)
        inner.pack(side="left", fill="x", expand=True, padx=12, pady=10)
        s_lbl = tk.Label(inner, text=t("privResumen"), bg=ui.GHOST_BG, fg=ui.ACCENT, font=ui.F("bold"),
                         anchor="w", justify="left")
        s_lbl.pack(fill="x")
        inner.bind("<Configure>", lambda e: s_lbl.configure(wraplength=max(240, e.width - 4)), add="+")
        for title, body in i18n.get("privItems"):
            dash._lbl(b, title, "bold").pack(fill="x", pady=(10, 2))
            holder = tk.Frame(b, bg=ui.SURFACE)
            holder.pack(fill="x")
            _wrapped(dash, holder, body, "muted")

        ui.Button(b, t("borrarTodoBoton"), self._erase_all, style="danger").pack(anchor="w", pady=(14, 0))

        # --- créditos
        card = dash._card(parent, t("creditosTitulo"))
        card.pack(fill="x")
        holder = tk.Frame(card.body, bg=ui.SURFACE)
        holder.pack(fill="x")
        _wrapped(dash, holder, t("creditosCuerpo"), "muted")

    def _erase_all(self):
        """Derecho de supresión: borra todos los datos locales y cierra la app (se vuelve a abrir como nueva)."""
        import backup
        top = self.d.top
        if not ui.confirm(top, t("borrarTodoTitulo"), t("borrarTodoTexto"), yes=t("borrar"), danger=True):
            return
        backup.erase_all()
        try:
            self.d.root.event_generate("<<QuitApp>>")
        except Exception:
            pass

    def _open(self, path):
        if not open_folder(path):
            self.notice.set(t("acercaNoAbre", p=path), "error")

    def _copy(self, path):
        top = self.d.top
        top.clipboard_clear()
        top.clipboard_append(path)
        self.notice.set(t("acercaRutaCopiada"), "success")
