"""Focus Relay Desktop
====================

Capa de bloqueo de aplicaciones que complementa la extensión de
navegador "Focus Relay for ESP-01S". Corre en segundo plano (ícono de
bandeja del sistema) y bloquea las apps de escritorio que elijas, solo
mientras el ESP-01S reporta una sesión de estudio activa.

Uso:
    python main.py

Ver README.md para instrucciones de inicio automático en Windows y Linux.
"""
import threading
import time
import tkinter as tk

from config import APP_VERSION, load_config, update_config
from esp_client import get_estado, url_of
from blocker import BlockEngine
import calendar_sync
import ui
import gui as gui_module
import services

import os
import sys
import traceback

if sys.stdout is None or sys.stderr is None:        # app empaquetada sin consola (Windows): evita errores al imprimir
    _null = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = sys.stdout or _null
    sys.stderr = sys.stderr or _null


pystray = None
HAVE_TRAY = False
TRAY_ERRORS = []                 # motivos por los que no se pudo crear el ícono (se muestran al usuario)
tray_ready = threading.Event()   # el ícono ya está visible en la bandeja


def _tray_backends():
    """Backends de pystray a probar, en orden. En Linux: AppIndicator (Mint/Ubuntu), GTK y Xorg."""
    forced = os.environ.get("PYSTRAY_BACKEND")
    if forced:
        return [forced]
    if sys.platform.startswith("linux"):
        return ["appindicator", "gtk", "xorg"]
    return [None]


def _tray_error(msg):
    if msg not in TRAY_ERRORS:
        TRAY_ERRORS.append(msg)


def _import_pystray(backend):
    """Importa pystray con un backend concreto (se vuelve a importar para cambiar de backend)."""
    global pystray
    for name in [m for m in sys.modules if m == "pystray" or m.startswith("pystray.")]:
        del sys.modules[name]
    if backend:
        os.environ["PYSTRAY_BACKEND"] = backend
    else:
        os.environ.pop("PYSTRAY_BACKEND", None)
    import pystray as _p
    pystray = _p
    return _p


try:
    _import_pystray(_tray_backends()[0])
    HAVE_TRAY = True
except Exception as _exc:         # sin ningún backend usable se prueba más tarde con los demás
    _tray_error(f"{_tray_backends()[0]}: {_exc}")
    HAVE_TRAY = bool(_tray_backends()[1:])

stop_event = threading.Event()
state_lock = threading.Lock()
shared_state = {"connected": False, "block_active": False, "suspend_until": 0.0,
                "estado": None, "fast_until": 0.0, "music": None, "rewards_version": 0}
tray_icon = None
PAUSE_SECONDS = 300  # pausa excepcional de 5 minutos, como en la extensión


def make_icon_image(mode=None, mode_colors=None):
    """Ícono de la bandeja: sigue al tema de color; con una sesión en marcha toma el color de su modo (T/C/P)."""
    import icon_art
    if mode in ("T", "C", "P"):
        col = ui.mode_color(mode, mode_colors)
        return icon_art.draw(64, ui.mix(col, "#000000", 0.45), col, "#ffffff")
    return icon_art.draw(64, ui.HERO_A, ui.HERO_C, ui.HERO_FG)


def session_label(estado):
    """Texto corto de la sesión en marcha (None si no hay): «Pomodoro · trabajo», «Temporizador»…"""
    if not estado or not estado.get("ejecutando"):
        return None
    from i18n import t
    modo = estado.get("modo")
    if modo == "P":
        return t("tipoPomodoroTrabajo" if estado.get("fase") == "W" else "tipoPomodoroDescanso")
    key = {"T": "tipoTemporizador", "C": "tipoCronometro"}.get(modo)
    return t(key) if key else None


def music_playing():
    ctl = shared_state.get("music")
    return bool(ctl and ctl.current)


def notify(title, message):
    """Notificación de escritorio: servicio del sistema en Linux (pystray no la soporta allí), bandeja en el resto."""
    import notifier
    if notifier.send(title, message, tray_icon if tray_ready.is_set() else None):
        return
    print(f"[{title}] {message}")


def local_events():
    """Avisos del temporizador propio (modo sin dispositivo): fin de bloque, descanso, etc."""
    import local_timer
    from i18n import t
    names = {"work_done": "notifTrabajoListo", "break_done": "notifDescansoListo",
             "timer_done": "notifTemporizadorListo", "chrono_limit": "notifCronometroLimite"}
    events = [e for e in local_timer.ENGINE.pop_events() if e["type"] in names]
    if events:                                                              # sonido suave: fin de sesión o cambio de modo
        import chime
        cfg = load_config()
        if cfg.get("sound_end", True):
            kind = {"work_done": "break", "break_done": "focus"}.get(events[-1]["type"], "done")
            chime.play(kind, cfg.get("sound_volume", 0.6))
    if any(e["type"] in ("work_done", "timer_done") for e in events):      # fin de un bloque de enfoque
        with state_lock:
            shared_state["celebrate"] = shared_state.get("celebrate", 0) + 1
    return [t(names[e["type"]]) for e in events]


def poller_loop(engine, background):
    last_esp_poll = 0.0
    last_enforce = 0.0
    icon_key = (ui.PALETTE, ui.THEME, None, False, False, False)
    while not stop_event.is_set():
        cfg = load_config()
        with state_lock:
            est = shared_state.get("estado")
        mode_now = est.get("modo") if session_label(est) else None
        with state_lock:
            blocking = bool(shared_state.get("block_active"))
            paused_now = time.time() < shared_state["suspend_until"]
        key = (ui.PALETTE, ui.THEME, mode_now, music_playing(), blocking, paused_now)
        if key != icon_key and tray_icon is not None:       # cambió el tema, el modo en marcha o la música
            icon_key = key
            try:
                tray_icon.icon = make_icon_image(mode_now, cfg.get("mode_colors"))
                label = session_label(est)
                tray_icon.title = "Focus Relay · " + __import__("i18n").t("traySesionActiva") + " · " + label if label else "Focus Relay Desktop"
                tray_icon.update_menu()
            except Exception:
                pass
        now = time.time()
        poll_every = max(cfg.get("poll_interval_ms", 1500), 300) / 1000.0
        if now < shared_state.get("fast_until", 0.0):      # el panel está abierto: reloj en vivo
            poll_every = 1.0 if url_of(cfg) == "local://" else 0.3     # en modo app el Panel ya lee el reloj directamente
            if cfg.get("eco_mode"):
                poll_every = max(poll_every, 1.0)

        if now - last_esp_poll >= poll_every:
            estado = get_estado(url_of(cfg))
            try:
                for ev in local_events():
                    notify("Focus Relay", ev)
            except Exception as exc:
                print(f"[Focus Relay] avisos: {exc}")
            last_esp_poll = now
            with state_lock:
                shared_state["connected"] = estado is not None
                shared_state["estado"] = estado
                shared_state["block_active"] = bool(estado and estado.get("bloqueoActivo"))
            try:
                background.process(cfg, estado)
            except Exception as exc:                        # una tarea de fondo nunca debe frenar el bloqueo
                print(f"[Focus Relay] tarea de fondo: {exc}")

        enforce_every = max(cfg.get("enforce_interval_ms", 1000), 300) / 1000.0
        if cfg.get("eco_mode"):
            enforce_every = max(enforce_every, 2.0)
        if now - last_enforce >= enforce_every - 0.01:             # revisar procesos es lo más caro del ciclo: solo a su ritmo
            last_enforce = now
            with state_lock:
                paused = now < shared_state["suspend_until"]
                block_active = (
                    shared_state["block_active"] and cfg.get("enabled", True) and not paused
                )
            engine.enforce(cfg, block_active)
        wait = enforce_every - (time.time() - last_enforce)
        if time.time() < shared_state.get("fast_until", 0.0):      # con el Panel abierto el sondeo sigue siendo ágil
            wait = min(wait, poll_every)
        stop_event.wait(max(0.1, wait))


def main():

    if "--diagnose" in sys.argv:                  # python3 main.py --diagnose
        import notifier
        print(notifier.diagnose())
        return

    import single_instance
    from config import config_dir
    if not single_instance.acquire(config_dir()):
        msg = "Focus Relay ya está abierto. Búscalo en el ícono de la bandeja del sistema."
        print("[Focus Relay] " + msg, file=sys.stderr)
        try:
            from tkinter import messagebox
            r = tk.Tk()
            r.withdraw()
            messagebox.showinfo("Focus Relay", msg)
            r.destroy()
        except Exception:
            pass
        return

    root = tk.Tk()
    root.withdraw()
    import ui
    from config import load_config
    ui.apply_text_scale(root, load_config().get("text_scale", 1.0))
    ui.refresh_theme()  # sin ventana principal visible; solo host del mainloop
    ui.set_window_icon(root)

    import block_popup
    engine = BlockEngine(notifier=notify, on_block=block_popup.show)   # avisa con una ventanita, no con notificación
    block_popup.pump(root)
    import esp_client
    import mascot
    import stats

    def mascot_state():
        cfg = load_config()
        est = esp_client.get_estado(esp_client.LOCAL) if cfg.get("connection_mode") == "local" else None
        with state_lock:
            return (est if est is not None else shared_state.get("estado")), shared_state.get("celebrate", 0)

    def mascot_streak():
        log = esp_client.get_log(esp_client.url_of(load_config())) or []
        return stats.streak(stats.calendar_counts([s for s in log if s.get("modo") != "D"]), None, stats.streak_days(load_config()))

    import watchdog                                       # si la ventana se cuelga, deja la pila de hilos en hang.log
    watchdog.Watchdog(root, watchdog.log_path(config_dir()), version=APP_VERSION).start()
    mascot_win = mascot.MascotWindow(root, mascot_state, load_config, update_config, mascot.texts, mascot_streak,
                        lambda: __import__("dashboard_gui").open_dashboard(root, shared_state, state_lock))
    shared_state["notify"] = notify                      # el panel avisa con él (p. ej. al iniciar una tarea)
    background = services.Background(shared_state, state_lock, notify)
    import bridge                                          # la extensión del navegador sigue el estado de esta app

    def bridge_state():
        """Estado para la extensión: el de la sesión + qué bloquear ahora (la app es la central de control)."""
        with state_lock:
            est = shared_state.get("estado")
            block = shared_state["block_active"]
            paused = time.time() < shared_state["suspend_until"]
        if not est:
            return None
        cfg = load_config()
        out = dict(est)
        out["actividad"] = ""
        if est.get("local"):
            import local_timer
            out["actividad"] = local_timer.ENGINE.activity
        out["web"] = {"bloquear": bool(block and cfg.get("enabled", True) and not paused), "pausado": paused,
                      "dominios": cfg.get("blocked_sites", []), "permitidos": cfg.get("allowed_sites", [])}
        return out

    def bridge_add_site(data):
        """«Bloquear este sitio» desde la extensión (solo agrega) o importación única de la lista antigua de la extensión."""
        import sites
        from config import save_config
        cfg = load_config()
        added = 0
        for raw in ([data.get("dominio")] if data.get("dominio") else []) + list(data.get("importar") or [])[:sites.MAX_SITES]:
            cfg["blocked_sites"], ok = sites.add(cfg.get("blocked_sites", []), raw)
            added += ok
        for raw in list(data.get("permitidos") or [])[:sites.MAX_SITES]:
            cfg["allowed_sites"], ok = sites.add(cfg.get("allowed_sites", []), raw)
            added += ok
        if added:
            save_config(cfg)
        return {"added": added, "total": len(cfg.get("blocked_sites", []))}

    bridge.start(bridge_state, lambda: load_config().get("bridge", True), load_config().get("bridge_port", bridge.PORT),
                 add_site=bridge_add_site)
    threading.Thread(target=poller_loop, args=(engine, background), daemon=True).start()
    calendar_sync.start_background(stop_event)  # mantiene al día el calendario suscrito por enlace

    def open_dashboard(icon=None, item=None):
        from dashboard_gui import open_dashboard as _open
        root.after(0, lambda: _open(root, shared_state, state_lock))

    def open_config(icon=None, item=None):
        root.after(0, lambda: gui_module.open_config_window(root, shared_state, state_lock))

    def open_suggestions(icon=None, item=None):
        from calendar_gui import open_calendar_window
        root.after(0, lambda: open_calendar_window(root))

    quitting = [False]

    def _really_quit():
        if quitting[0]:
            return
        quitting[0] = True
        stop_event.set()
        if tray_icon is not None:
            try:
                tray_icon.stop()
            except Exception:
                pass
        wait = 0.0
        try:
            wait = mascot_win.say_goodbye()               # la mascota se despide un momento antes de cerrar
        except Exception as exc:
            print(f"[Focus Relay] mascota: {exc}")
        root.after(int(wait * 1000), root.destroy)

    quit_asking = [False]

    def _ask_quit():
        """Con modo estricto y una sesión en marcha, cerrar la app exige escribir un código largo."""
        import guard
        from i18n import t
        if quit_asking[0]:
            return
        with state_lock:
            est = shared_state.get("estado")
        cfg0 = load_config()
        if not guard.quit_locked(cfg0, est):
            if not guard.quit_needs_confirm(cfg0, est):
                _really_quit()
                return
            quit_asking[0] = True                            # confirmación simple (opcional) si hay una sesión en marcha
            try:
                import mascot
                from dashboard_gui import open_dashboard as _open, _open as _state
                _open(root, shared_state, state_lock)
                mascot.set_wary(True)
                try:
                    ok = ui.confirm(_state.get("top"), t("quitConfTitulo"), t("quitConfTexto"), yes=t("quitBoton"), danger=True)
                finally:
                    mascot.set_wary(False)
                if ok:
                    _really_quit()
            except Exception as exc:
                print(f"[Focus Relay] cierre: {exc}")
                _really_quit()
            finally:
                quit_asking[0] = False
            return
        quit_asking[0] = True
        try:
            from dashboard_gui import open_dashboard as _open, _open as _state
            _open(root, shared_state, state_lock)
            parent = _state.get("top")
            import mascot
            cfg = load_config()
            mascot.set_wary(True)                            # Brote te mira raro mientras dudas
            try:
                ok = ui.ask_code(parent, t("quitTitulo"), t("quitTexto"), guard.new_code(3, 4, guard.code_mixed(cfg)),
                                 t("quitBoton"), t("cancelar"), t("estrictoCodigoMal"), guard.code_mixed(cfg))
            finally:
                mascot.set_wary(False)
            if ok:
                _really_quit()
        except Exception as exc:
            print(f"[Focus Relay] cierre: {exc}")        # ante un fallo de la interfaz no se deja la app imposible de cerrar
            _really_quit()
        finally:
            quit_asking[0] = False

    def quit_app(icon=None, item=None):
        root.after(0, _ask_quit)

    def is_paused():
        with state_lock:
            return time.time() < shared_state["suspend_until"]

    def pause_allowed():
        # Igual que la extensión: el modo estricto no permite pausa. Solo tiene sentido con el bloqueo actuando ahora.
        cfg = load_config()
        with state_lock:
            blocking = bool(shared_state.get("block_active"))
        return (cfg.get("mode") != "strict" and not cfg.get("strict_mode") and cfg.get("enabled", True)
                and blocking and not is_paused())

    def idle_local():
        """Modo app y sin sesión en marcha: se puede iniciar una desde la bandeja."""
        with state_lock:
            est = shared_state.get("estado")
        return bool(est and est.get("local") and not est.get("ejecutando"))

    def start_session_tray(icon=None, item=None):
        import esp_client
        cfg = load_config()
        act = (cfg.get("next_activity") or "").strip()
        esp_client.toggle_run(esp_client.LOCAL, act)
        with state_lock:
            shared_state["fast_until"] = time.time() + 3

    def pause_5min(icon=None, item=None):
        if not pause_allowed():
            return
        with state_lock:
            shared_state["suspend_until"] = time.time() + PAUSE_SECONDS
        notify("Focus Relay", __import__("i18n").t("trayPausado"))

    def resume_now(icon=None, item=None):
        with state_lock:
            shared_state["suspend_until"] = 0.0

    def stop_music(icon=None, item=None):
        ctl = shared_state.get("music")
        if ctl:
            ctl.stop()
        try:
            if tray_icon is not None:
                tray_icon.update_menu()
        except Exception:
            pass

    def active_text(item):
        with state_lock:
            label = session_label(shared_state.get("estado"))
        from i18n import t
        return f"● {t('traySesionActiva')} · {label}" if label else ""

    def toggle_mascot(icon=None, item=None):
        cfg = load_config()
        update_config(mascot=not cfg.get("mascot", True))

    def _t(key):
        from i18n import t
        return t(key)

    def menu_items():
        return (
            pystray.MenuItem(active_text, None, enabled=False, visible=lambda i: bool(active_text(i))),
            pystray.MenuItem(lambda i: _t("trayAbrir"), open_dashboard, default=True),
            pystray.MenuItem(lambda i: _t("trayIniciar"), start_session_tray, visible=lambda i: idle_local()),
            pystray.MenuItem(lambda i: _t("trayDetenerMusica"), stop_music, visible=lambda i: music_playing()),
            pystray.MenuItem(lambda i: _t("trayMascota"), toggle_mascot),
            pystray.MenuItem(lambda i: _t("trayBloqueoApps"), open_config),
            pystray.MenuItem(lambda i: _t("traySugeridas"), open_suggestions),
            pystray.MenuItem(lambda i: _t("trayPausar"), pause_5min, visible=lambda i: pause_allowed()),
            pystray.MenuItem(lambda i: _t("trayReanudar"), resume_now, visible=lambda i: is_paused()),
            pystray.MenuItem(lambda i: _t("traySalir"), quit_app),
        )

    def tray_worker():
        """Prueba los backends de bandeja uno tras otro hasta que el ícono quede visible."""
        global tray_icon
        for backend in _tray_backends():
            if stop_event.is_set():
                return
            try:
                if backend == "appindicator":
                    import notifier
                    if notifier.tray_watcher() is False:          # nadie mostraría el ícono: pasa al siguiente backend
                        _tray_error("appindicator: el escritorio no tiene StatusNotifierWatcher (applet de bandeja desactivado)")
                        continue
                _import_pystray(backend)
                icon = pystray.Icon("focus_relay_desktop", make_icon_image(), "Focus Relay Desktop",
                                    pystray.Menu(*menu_items()))
                tray_icon = icon

                def setup(i):
                    i.visible = True
                    tray_ready.set()
                icon.run(setup=setup)         # bloquea hasta icon.stop()
                if stop_event.is_set() or tray_ready.is_set():
                    return
                _tray_error(f"{backend}: la bandeja se cerró sin mostrar el ícono")
            except Exception as exc:
                _tray_error(f"{backend}: {exc or type(exc).__name__}")
                traceback.print_exc()
            tray_icon = None
        # ningún backend funcionó: la app sigue usable desde el Panel

    if HAVE_TRAY or TRAY_ERRORS:
        threading.Thread(target=tray_worker, daemon=True).start()

    def check_tray():
        if tray_ready.is_set() or stop_event.is_set():
            return
        shared_state["no_tray"] = True
        detail = "\n".join(TRAY_ERRORS[-3:]) or "sin respuesta del escritorio"
        hint = ("Instala los paquetes de bandeja y vuelve a abrir:\n"
                "  pip3 install --break-system-packages -r requirements.txt   (si falta pystray)\n"
                "  sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 libnotify-bin\n"
                "Para ver qué falta:  python3 main.py --diagnose\n"
                "Si usas un entorno virtual, créalo con --system-site-packages.\n\n"
                "Mientras tanto la app funciona desde esta ventana; al cerrarla, el programa termina.") \
            if sys.platform.startswith("linux") else "La app funciona desde esta ventana."
        msg = f"No se pudo mostrar el ícono de la bandeja.\n\n{detail}\n\n{hint}"
        print("[Focus Relay] " + msg, file=sys.stderr)
        try:
            from tkinter import messagebox
            parent = None
            import dashboard_gui
            parent = dashboard_gui._open.get("top")
            messagebox.showwarning("Focus Relay", msg, parent=parent)
        except Exception:
            pass

    root.after(5000, check_tray)
    if "--background" not in sys.argv:
        root.after(300, open_dashboard)       # al iniciar a mano se ve el Panel; el autoinicio usa --background
    elif load_config().get("startup_tasks"):  # autoinicio + opción: directo a Tareas para planificar lo que toca hacer
        def open_tasks():
            from dashboard_gui import open_dashboard as _open
            _open(root, shared_state, state_lock, "tareas")
        root.after(1500, open_tasks)

    root.bind("<<QuitApp>>", lambda e: quit_app())
    root.protocol("WM_DELETE_WINDOW", quit_app)
    root.mainloop()


if __name__ == "__main__":
    main()
