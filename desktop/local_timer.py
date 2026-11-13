"""Temporizador propio de la app (modo "Solo en la app", sin ESP-01S).

Reproduce lo que hace el firmware: Temporizador, Cronómetro y Pomodoro (trabajo → descanso corto,
descanso largo cada N ciclos), el mismo formato de /estado, el registro de sesiones (las < 5 s no
se guardan) y el bloqueo solo durante el trabajo del Pomodoro. Todo se calcula con la hora del
sistema, así que sigue siendo exacto aunque la app esté ocupada o el equipo se suspenda.

El motor es pasivo: `snapshot()` avanza el reloj hasta "ahora"; lo consulta el hilo de fondo
cada ~0,5-1,5 s. Los avisos (fin de bloque, etc.) quedan en una cola que recoge `pop_events()`.
"""
import copy
import json
import os
import random
import threading
import time

from config import config_dir, load_config, save_config

LOCAL_URL = "local://"
MAX_SECONDS = 5999            # 99:59, igual que el display del dispositivo
MIN_LOG_SECONDS = 5
CATCH_UP_SECONDS = 90          # si el equipo estuvo suspendido más que esto, el Pomodoro no encadena fases «fantasma»
MAX_LOG = 20000                 # el historial completo alimenta estadísticas y logros
DEFAULT_DURATIONS = {"minutos": 25, "pomTrabajo": 25, "pomDescanso": 5, "pomDescansoLargo": 15, "pomCiclos": 4}
_LIMITS = {"minutos": (1, 99), "pomTrabajo": (1, 99), "pomDescanso": (1, 99),
           "pomDescansoLargo": (1, 99), "pomCiclos": (1, 10)}


def log_path():
    return os.path.join(config_dir(), "local_sessions.json")


def durations():
    d = copy.deepcopy(DEFAULT_DURATIONS)
    saved = load_config().get("local_durations") or {}
    for k, (lo, hi) in _LIMITS.items():
        try:
            d[k] = max(lo, min(hi, int(saved.get(k, d[k]))))
        except (TypeError, ValueError):
            pass
    return d


class LocalTimer:
    def __init__(self):
        self.lock = threading.RLock()
        self.mode, self.phase, self.running = "T", "-", False
        self.start_at = self.end_at = 0.0
        self.total = 0
        self.cycles = 0
        self.run_id = 0
        self.completed_work = 0
        self.cancel_id = 0
        self.events = []
        self.activity = ""
        self.quick_minutes = None
        self._log = None

    # ---------------------------------------------------------------- registro
    def _load_log(self):
        if self._log is None:
            try:
                with open(log_path(), encoding="utf-8") as f:
                    data = json.load(f)
                self._log = [e for e in data if isinstance(e, dict) and isinstance(e.get("duracion_seg"), (int, float))] \
                    if isinstance(data, list) else []
            except (OSError, ValueError):
                self._log = []
        return self._log

    def _save_log(self):
        path = log_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._log, f, ensure_ascii=False)
        os.replace(tmp, path)

    def _record(self, seconds, kind, completed, when):
        seconds = int(seconds)
        if seconds < MIN_LOG_SECONDS:
            return
        entry = {"duracion_seg": seconds, "modo": kind, "epoch": int(when)}
        if self.activity:
            entry["actividad"] = self.activity
        entry["completada"] = bool(completed)
        log = self._load_log()
        log.append(entry)
        del log[:-MAX_LOG]
        try:
            self._save_log()
        except OSError:
            pass

    # ---------------------------------------------------------------- avance
    def _idle_seconds(self):
        d = durations()
        if self.mode == "T":
            return (self.quick_minutes or d["minutos"]) * 60
        if self.mode == "P":
            return d["pomTrabajo"] * 60
        return 0

    def _tick(self, now):
        guard = 0
        while self.running and guard < 60:
            guard += 1
            if self.mode == "C":
                if now - self.start_at >= MAX_SECONDS:
                    self._record(MAX_SECONDS, "C", True, self.start_at + MAX_SECONDS)
                    self.events.append({"type": "chrono_limit"})
                    self._finish()
                break
            if now < self.end_at:
                break
            at = self.end_at
            if self.mode == "T":
                self._record(self.total, "T", True, at)
                self.events.append({"type": "timer_done"})
                self._finish()
                break
            d = durations()                       # Pomodoro: encadena fases
            if self.phase == "W":
                self._record(self.total, "W", True, at)
                self.completed_work += 1
                self.cycles += 1
                self.events.append({"type": "work_done"})
                long_break = self.cycles % d["pomCiclos"] == 0
                self.phase, self.total = "D", (d["pomDescansoLargo"] if long_break else d["pomDescanso"]) * 60
            else:
                self._record(self.total, "D", True, at)
                self.events.append({"type": "break_done"})
                self.phase, self.total = "W", d["pomTrabajo"] * 60
            if now - at > CATCH_UP_SECONDS:        # el equipo durmió o la app estuvo parada: se cierra aquí, sin premiar horas ficticias
                self._finish()
                break
            self.end_at = at + self.total

    def _finish(self):
        self.running, self.phase, self.activity, self.quick_minutes = False, "-", "", None

    def _remaining(self, now):
        return max(0, int(self.end_at - now + 0.999))

    # ---------------------------------------------------------------- API de estado
    def snapshot(self):
        with self.lock:
            now = time.time()
            self._tick(now)
            next_ms = None
            if self.running:
                if self.mode == "C":
                    secs = int(now - self.start_at)
                    next_ms = int((1.0 - ((now - self.start_at) % 1.0)) * 1000)
                else:
                    secs = self._remaining(now)
                    left = self.end_at - now                      # el número cambia cuando `left` cruza un entero
                    next_ms = int(((left % 1.0) or 1.0) * 1000)
            else:
                secs = self._idle_seconds()
            return {
                "proximoMs": next_ms,
                "modo": self.mode, "fase": self.phase, "segundos": secs, "ejecutando": self.running,
                "bloqueoActivo": bool(self.running and (
                    (self.mode == "P" and self.phase == "W")
                    or (self.mode == "T" and load_config().get("block_in_timer", True))
                    or (self.mode == "C" and load_config().get("block_in_chrono", False)))),
                "cancelacionFisicaId": self.cancel_id, "idArranque": self.run_id,
                "sesionesTrabajoCompletadas": self.completed_work, "local": True,
            }

    def pop_events(self):
        with self.lock:
            ev, self.events = self.events, []
            return ev

    # ---------------------------------------------------------------- acciones
    def start(self, minutes=None, activity=""):
        with self.lock:
            self._tick(time.time())
            if self.running:
                return False
            now = time.time()
            self.run_id = random.getrandbits(32)
            self.activity = (activity or "").strip()
            self.cycles = 0
            self.quick_minutes = minutes
            if self.mode == "C":
                self.start_at, self.phase = now, "-"
            elif self.mode == "T":
                self.total = (minutes or durations()["minutos"]) * 60
                self.start_at, self.end_at, self.phase = now, now + self.total, "-"
            else:
                self.total = durations()["pomTrabajo"] * 60
                self.start_at, self.end_at, self.phase = now, now + self.total, "W"
            self.running = True
            return True

    def stop(self):
        with self.lock:
            now = time.time()
            self._tick(now)
            if not self.running:
                return False
            if self.mode == "C":
                self._record(now - self.start_at, "C", False, now)
            else:
                self._record(self.total - self._remaining(now), "T" if self.mode == "T" else self.phase, False, now)
                if self.mode == "T" or self.phase == "W":
                    self.cancel_id += 1
            self._finish()
            return True

    def toggle(self, activity=""):
        with self.lock:
            return self.stop() if self.running else self.start(activity=activity)

    def set_mode(self, mode):
        with self.lock:
            if mode not in ("T", "C", "P"):
                return False
            if self.running:
                self.stop()
            self.mode, self.quick_minutes = mode, None
            return True

    def extend(self, seconds):
        with self.lock:
            now = time.time()
            self._tick(now)
            if not self.running or self.mode == "C":
                return False
            add = max(0, min(int(seconds), int(now + MAX_SECONDS - self.end_at)))
            self.end_at += add
            self.total += add
            return True

    # ---------------------------------------------------------------- historial
    def log_signature(self):
        """(cantidad, epoch de la última) — permite saber si el historial cambió sin copiarlo."""
        with self.lock:
            log = self._load_log()
            return len(log), (log[-1].get("epoch", 0) if log else 0)

    def get_log(self):
        with self.lock:
            return copy.deepcopy(self._load_log())

    def clear_log(self):
        with self.lock:
            self._log = []
            try:
                self._save_log()
            except OSError:
                return False
            return True

    def tag(self, index, activity):
        with self.lock:
            log = self._load_log()
            if not 0 <= index < len(log):
                return False
            if activity:
                log[index]["actividad"] = activity
            else:
                log[index].pop("actividad", None)
            try:
                self._save_log()
            except OSError:
                return False
            return True


ENGINE = LocalTimer()


def get_device_config():
    d = durations()
    return d


def save_device_config(values):
    cfg = load_config()
    saved = dict(cfg.get("local_durations") or {})
    for k, (lo, hi) in _LIMITS.items():
        if k in values:
            try:
                saved[k] = max(lo, min(hi, int(values[k])))
            except (TypeError, ValueError):
                pass
    cfg["local_durations"] = saved
    save_config(cfg)
    return True
