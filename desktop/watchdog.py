"""Vigilante del hilo de la interfaz: si la ventana deja de responder, deja un informe en `hang.log`.

Un cuelgue del hilo principal congela la ventana, la mascota y el menú de la bandeja a la vez. Este módulo comprueba
cada pocos segundos que el hilo siga vivo (un `after` que marca la hora) y, si pasa el plazo sin latidos, guarda la pila
de TODOS los hilos en la carpeta de datos. Con ese archivo se ve exactamente dónde quedó atascado.
"""
import faulthandler
import os
import threading
import time


class Watchdog:
    def __init__(self, root, path, limit=8.0, poll=2.0, version=""):
        self.root, self.path, self.limit, self.poll, self.version = root, path, limit, poll, version
        self.last = time.time()
        self.dumped = False
        self._stop = threading.Event()

    def start(self):
        self._beat()
        threading.Thread(target=self._watch, name="ui-watchdog", daemon=True).start()
        return self

    def stop(self):
        self._stop.set()

    def _beat(self):
        self.last = time.time()
        self.dumped = False
        if not self._stop.is_set():
            try:
                self.root.after(500, self._beat)
            except Exception:
                pass

    def stalled(self, now=None):
        return ((time.time() if now is None else now) - self.last) > self.limit

    def dump(self):
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')}  Focus Relay {self.version}: "
                        f"la interfaz no responde hace {self.limit:.0f} s ===\n")
                f.flush()
                faulthandler.dump_traceback(file=f, all_threads=True)
            self.dumped = True
        except OSError:
            self.dumped = True

    def _watch(self):
        while not self._stop.wait(self.poll):
            if self.stalled() and not self.dumped:
                self.dump()
        return


def log_path(directory):
    return os.path.join(directory, "hang.log")
