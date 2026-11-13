"""Tareas de fondo de la app: música por modo, premios, sincronización de hora e
importación de datos del firmware antiguo. `Background.process()` se llama desde el
hilo que consulta el estado del ESP-01S (main.py)."""
import queue
import threading
import time

import chime
import esp_client
import music
import rewards
import trophies
from config import load_config, load_data, save_config, save_data


class MusicController:
    """Ejecuta las órdenes de música en un hilo aparte (conectar a una radio puede tardar)."""

    def __init__(self):
        self.player = music.MusicPlayer()
        self.offline = ""                 # id de la radio que no pudo sonar por falta de internet ("" = todo bien)
        self.volume = 0.35
        self._last_check = 0.0
        self._q = queue.Queue()
        threading.Thread(target=self._loop, daemon=True).start()

    @property
    def current(self):
        return self.player.current

    @property
    def error(self):
        return self.player.error

    def play(self, preset_id, volume):
        self.volume = volume
        self._q.put(("play", preset_id, volume))

    def stop(self):
        self.offline = ""
        self._q.put(("stop",))

    def check_online(self, running):
        """Cada ~8 s pide revisar la conexión. La revisión se hace en el hilo de la música, nunca en el sondeo."""
        now = time.time()
        if now - self._last_check < 8:
            return
        self._last_check = now
        self._q.put(("check", running))

    def _check(self, running):
        """Si una radio no pudo sonar vuelve a intentarlo al volver internet; si estaba sonando y se cae, avisa."""
        if self.offline and running:
            if music.has_internet():
                self.player.play(self.offline, self.volume)
                self.offline = "" if self.player.current else self.offline
        elif self.player.current and music.is_stream(self.player.current) and not music.has_internet():
            self.offline = self.player.current
            self.player.stop()

    def set_volume(self, volume):
        self.player.set_volume(volume)

    @staticmethod
    def collapse(cmds):
        """De varias órdenes acumuladas solo importa la última de música; las revisiones de conexión solo valen si no hay otra."""
        real = [c for c in cmds if c[0] != "check"]
        return real[-1] if real else cmds[-1]

    def _loop(self):
        while True:
            cmds = [self._q.get()]
            while not self._q.empty():
                cmds.append(self._q.get_nowait())
            cmd = self.collapse(cmds)
            try:
                if cmd[0] == "check":
                    self._check(cmd[1])
                elif cmd[0] == "play":
                    if music.is_stream(cmd[1]) and not music.has_internet():
                        self.player.stop()
                        self.offline = cmd[1]                  # el panel lo muestra de forma visible
                    else:
                        self.offline = ""
                        if not self.player.play(cmd[1], cmd[2]) and music.is_stream(cmd[1]) and not music.has_internet():
                            self.offline = cmd[1]              # se cayó justo al conectar
                elif cmd[0] == "stop_keep":                   # se cayó internet con la radio sonando: queda marcada
                    self.player.stop()
                else:
                    self.player.stop()
            except Exception:
                pass


class Background:
    def __init__(self, shared_state, state_lock, notifier):
        self.state = shared_state
        self.lock = state_lock
        self.notify = notifier
        self.music = MusicController()
        shared_state["music"] = self.music
        self._last_running = None
        self._last_key = ""
        self._was_connected = False
        self._last_sync = 0.0

    # --- punto de entrada ---------------------------------------------------
    def process(self, cfg, estado):
        connected = estado is not None
        if connected and (not self._was_connected or time.time() - self._last_sync > 1800):
            self._sync_time(cfg)
            self._import_legacy(cfg)
        self._was_connected = connected
        self._celebrate_check(cfg, estado)
        self._warn_end(cfg, estado)
        self._music(cfg, estado)
        self.music.check_online(bool(estado and estado.get("ejecutando")))
        if connected:
            if estado.get("local"):
                self._local_trophies(cfg)
            else:
                self._rewards(cfg, estado)

    # --- fin de sesión (dispositivo): el ESP no avisa, se deduce de dos lecturas seguidas ----------------
    def _celebrate_check(self, cfg, estado):
        prev, self._prev_estado = getattr(self, "_prev_estado", None), estado
        if estado and estado.get("ejecutando"):                    # duración de la sesión: el mayor tiempo visto en la cuenta atrás
            run = estado.get("idArranque")
            if not prev or not prev.get("ejecutando") or prev.get("idArranque") != run \
                    or prev.get("fase") != estado.get("fase"):
                self._run_peak = 0
            self._run_peak = max(getattr(self, "_run_peak", 0), int(estado.get("segundos") or 0))
        if not prev or not estado or estado.get("local"):          # el modo app avisa con eventos propios
            return
        if not prev.get("ejecutando") or prev.get("modo") not in ("T", "P"):
            return
        near_end = int(prev.get("segundos") or 0) <= 4
        moved_on = (not estado.get("ejecutando")) or estado.get("fase") != prev.get("fase") \
            or estado.get("idArranque") != prev.get("idArranque")
        if not (near_end and moved_on):
            return
        if cfg.get("sound_end", True):                            # sonido de fin de bloque o de cambio de modo
            kind = "done" if prev.get("modo") == "T" else ("break" if prev.get("fase") == "W" else "focus")
            chime.play(kind, cfg.get("sound_volume", 0.6))
        if prev.get("modo") == "P" and prev.get("fase") != "W":    # el fin de un descanso no se celebra
            return
        with self.lock:
            self.state["celebrate"] = self.state.get("celebrate", 0) + 1
        if prev.get("modo") == "T" and getattr(self, "_run_peak", 0) >= trophies.MIN_PIECE_SECONDS:
            self._award_device_timer(prev)                        # el firmware solo cuenta Pomodoros: el Temporizador se premia aquí

    # --- aviso previo: "faltan N min" (una sola vez por bloque) ----------------------------------------
    def _warn_end(self, cfg, estado):
        n = int(cfg.get("warn_end_min") or 0)
        last, self._warn_last = getattr(self, "_warn_last", None), None
        if not estado or n <= 0 or not estado.get("ejecutando"):
            return
        if estado.get("modo") == "C" or (estado.get("modo") == "P" and estado.get("fase") == "D"):
            return
        key = (estado.get("idArranque"), estado.get("fase"))
        secs = int(estado.get("segundos") or 0)
        self._warn_last = (key, secs)
        limit = n * 60
        if last and last[0] == key and last[1] > limit >= secs > limit - 6:
            from i18n import t
            try:
                self.notify("Focus Relay", t("avisoFaltan", n=n))
            except Exception:
                pass

    # --- hora e importación -------------------------------------------------
    def _sync_time(self, cfg):
        if esp_client.sync_time(esp_client.url_of(cfg)):
            self._last_sync = time.time()

    def _import_legacy(self, cfg):
        """Una sola vez: trae etiquetas y frases que el firmware antiguo guardaba en el ESP."""
        if cfg.get("legacy_imported"):
            return
        url = esp_client.url_of(cfg)
        tags = esp_client.get_legacy_list(url, "/actividades")
        phrases = esp_client.get_legacy_list(url, "/frases")
        if tags is None or phrases is None:
            return
        fresh = load_config()
        for tag in tags:
            if tag and tag not in fresh["tags"]:
                fresh["tags"].append(tag)
        for ph in phrases:
            if ph and ph not in fresh["phrases"]:
                fresh["phrases"].append(ph)
        fresh["legacy_imported"] = True
        save_config(fresh)
        if tags or phrases:
            self.notify("Focus Relay", "Se importaron las etiquetas y frases guardadas en el ESP-01S.")

    # --- trofeos ------------------------------------------------------------
    def _toast(self, kind, text):
        """Aviso dentro de la app (lo muestra el panel) y notificación del sistema."""
        with self.lock:
            self.state.setdefault("toasts", []).append({"kind": kind, "text": text})
        try:
            self.notify("Focus Relay", text)
        except Exception:
            pass

    def _announce(self, cfg, won, new_ach):
        import i18n
        i18n.set_language(cfg.get("language", "es"))
        names = [i18n.t("logro_" + a["family"], n=a["goal"]) for a in new_ach[:3]]
        if won or names:                                  # el panel lo muestra junto al confeti al terminar la sesión
            with self.lock:
                self.state.setdefault("won", []).append({
                    "t": time.time(), "count": len(won),
                    "piece": ({"icon": won[-1]["icon"], "color": won[-1]["color"]} if won else None),
                    "ach": names, "caption": i18n.t("toastPieza"),
                    "ach_caption": [i18n.t("toastLogro", name=n) for n in names]})
        if won:
            with self.lock:
                self.state["rewards_version"] = self.state.get("rewards_version", 0) + 1
            self._toast("piece", "🏆 " + ("+" + str(len(won)) + " " if len(won) > 1 else "") + won[-1]["icon"] + "  " + i18n.t("toastPieza"))
        for a in new_ach[:3]:
            self._toast("ach", "🏆 " + i18n.t("toastLogro", name=i18n.t("logro_" + a["family"], n=a["goal"])))

    def _local_trophies(self, cfg):
        """Modo app: piezas y logros se deducen del historial; solo se recalcula cuando cambia."""
        import insights
        import local_timer
        import tasks
        eng = local_timer.ENGINE
        with self.lock:
            dirty = self.state.pop("trophy_dirty", False)
        sig = eng.log_signature()
        if sig == getattr(self, "_trophy_sig", None) and not dirty:
            return
        self._trophy_sig = sig
        log = eng.get_log()
        data = load_data()
        won = trophies.award_from_log(log, data, cfg.get("reward_categories", []))
        try:                                                    # los logros cuentan también las sesiones del dispositivo guardadas
            import esp_client
            everything = esp_client.get_log(esp_client.LOCAL) or log
        except Exception:
            everything = log
        tot = insights.totals(everything, tasks.done_by_date(tasks.load()))
        new_ach = trophies.check_achievements(tot, data)
        save_data(data)
        self._announce(cfg, won if len(won) <= 3 else won[-1:], new_ach)    # un historial antiguo no inunda de avisos

    def _award_device_timer(self, prev):
        cfg = load_config()
        data = load_data()
        piece = rewards.make_piece(f"T{prev.get('idArranque')}", int(time.time()), cfg.get("reward_categories", []))
        data["rewards"] = (list(data.get("rewards", [])) + [piece])[-rewards.MAX_KEPT:]
        save_data(data)
        self._announce(cfg, [piece], [])

    # --- premios (dispositivo: pomodoros según el contador del firmware) ----------

    def _rewards(self, cfg, estado):
        data = load_data()
        new_list, new_token, won = rewards.collect(
            estado, data.get("last_completion_token", ""), data.get("rewards", []),
            cfg.get("reward_categories", []))
        if new_token != data.get("last_completion_token") or won:
            data["rewards"], data["last_completion_token"] = new_list, new_token
            save_data(data)
        if won:
            self._announce(cfg, won, [])

    # --- música (misma lógica que la extensión) -------------------------------
    def _music(self, cfg, estado):
        running = bool(estado and estado.get("ejecutando"))
        key = music.music_key(estado)
        prev = self._last_running
        if estado is None:
            if prev and cfg.get("music_auto_stop", True):
                self.music.stop()
            self._last_running = False if prev is not None else None
            return
        if prev is None:                       # primera lectura: solo se toma como referencia
            self._last_running, self._last_key = running, key
            return
        if running and cfg.get("music_auto_start", True) and (not prev or key != self._last_key):
            preset = (cfg.get("music_by_mode") or {}).get(key)
            if preset and preset != "none":
                self.music.play(preset, cfg.get("music_volume", 0.35))
            else:
                self.music.stop()
        if prev and not running and cfg.get("music_auto_stop", True):
            self.music.stop()
        self._last_running, self._last_key = running, key
