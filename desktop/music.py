"""Música de concentración por modo (misma idea que la extensión).

- Ruidos marrón / blanco / rosa: se generan en el propio computador.
- Radios SomaFM (Groove Salad, Drone Zone, Deep Space One): stream MP3 por internet.

Usa `miniaudio` (una sola dependencia, con decodificador MP3 incluido, sin ffmpeg ni VLC).
Si no está instalado la app sigue funcionando y solo avisa que falta.
"""
import os
import queue
import random
import threading
import urllib.request
from array import array

try:
    import miniaudio
    AVAILABLE = True
except Exception:                       # pragma: no cover - depende del entorno
    miniaudio = None
    AVAILABLE = False

# id -> (clave de texto, tipo, url)
CATALOG = {
    "brown": ("mBrown", "brown", None),
    "white": ("mWhite", "white", None),
    "pink": ("mPink", "pink", None),
    "groove": ("mGroove", "stream", "https://ice5.somafm.com/groovesalad-128-mp3"),
    "drone": ("mDrone", "stream", "https://ice5.somafm.com/dronezone-128-mp3"),
    "space": ("mSpace", "stream", "https://ice5.somafm.com/deepspaceone-128-mp3"),
    "none": ("mNone", "none", None),
}
CATALOG_ORDER = ["brown", "white", "pink", "groove", "drone", "space", "none"]
MODE_KEYS = ["T", "C", "W", "D"]           # Temporizador, Cronómetro, Pomodoro trabajo, Pomodoro descanso
RATE = 44100


def is_stream(preset_id):
    return preset_id in CATALOG and CATALOG[preset_id][1] == "stream"


_PROBES = ("1.1.1.1", "8.8.8.8", "9.0.0.9")


def has_internet(timeout=1.5):
    """¿Hay salida a internet? Abre una conexión TCP corta a varias IP públicas EN PARALELO y sin usar DNS (con una red
    sin salida, resolver nombres puede tardar decenas de segundos y dejaba la app esperando). Tarda como máximo
    ~`timeout` segundos. FOCUS_RELAY_OFFLINE=1 fuerza «sin conexión» (pruebas)."""
    if os.environ.get("FOCUS_RELAY_OFFLINE") == "1":
        return False
    import socket
    ok = threading.Event()

    def probe(ip):
        try:
            socket.create_connection((ip, 443), timeout=timeout).close()
            ok.set()
        except OSError:
            pass
    for ip in _PROBES:
        threading.Thread(target=probe, args=(ip,), daemon=True).start()
    ok.wait(timeout + 0.3)
    return ok.is_set()


def music_key(estado):
    """Clave de modo para elegir música: T, C, W (trabajo) o D (descanso)."""
    if not estado:
        return ""
    if estado.get("modo") == "P":
        return "D" if estado.get("fase") == "D" else "W"
    return estado.get("modo", "")


def _noise_buffer(kind, volume, seconds=4):
    """Buffer estéreo int16 en bucle (se regenera si cambia el volumen)."""
    n = RATE * seconds
    out = array("h", bytes(n * 4))
    last = pink = 0.0
    gain = max(0.0, min(1.0, volume)) * 32767
    rnd = random.random
    for i in range(n):
        w = rnd() * 2 - 1
        if kind == "brown":
            last = (last + 0.02 * w) / 1.02
            v = last * 3.5
        elif kind == "pink":
            pink = 0.985 * pink + 0.15 * w
            v = pink * 0.7
        else:
            v = w * 0.55
        s = int(max(-1.0, min(1.0, v)) * gain)
        out[2 * i] = s
        out[2 * i + 1] = s
    return out


def _open_with_deadline(url, seconds):
    """urlopen con plazo total: el `timeout` de urllib no cubre la resolución DNS, que sin internet puede colgarse."""
    box = {}

    def work():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FocusRelayDesktop"})
            box["resp"] = urllib.request.urlopen(req, timeout=8)
        except Exception as exc:
            box["err"] = exc
    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(seconds)
    if "resp" in box:
        return box["resp"]
    raise box.get("err") or TimeoutError("sin respuesta de la radio")


class _HttpSource(miniaudio.StreamableSource if AVAILABLE else object):
    """Lee la radio en un hilo aparte para que la red no corte el audio."""

    def __init__(self, url, stop_event):
        self._resp = _open_with_deadline(url, 8.0)
        self._q = queue.Queue(maxsize=64)
        self._stop = stop_event
        self._buf = b""
        threading.Thread(target=self._fill, daemon=True).start()

    def _fill(self):
        try:
            while not self._stop.is_set():
                chunk = self._resp.read(8192)
                if not chunk:
                    break
                while not self._stop.is_set():
                    try:
                        self._q.put(chunk, timeout=0.5)
                        break
                    except queue.Full:
                        continue
        except Exception:
            pass
        finally:
            try:
                self._q.put(b"", timeout=1)
            except queue.Full:
                pass

    def read(self, num_bytes):
        while len(self._buf) < num_bytes and not self._stop.is_set():
            try:
                chunk = self._q.get(timeout=1)
            except queue.Empty:
                continue
            if not chunk:
                break
            self._buf += chunk
        out, self._buf = self._buf[:num_bytes], self._buf[num_bytes:]
        return out

    def close(self):
        try:
            self._resp.close()
        except Exception:
            pass


class MusicPlayer:
    def __init__(self):
        self.current = ""            # id del preset sonando ("" = nada)
        self.error = ""
        self._device = None
        self._stop = threading.Event()
        self._volume = 0.35
        self._lock = threading.Lock()

    @property
    def playing(self):
        return bool(self.current)

    def _new_device(self):
        backends = None
        if os.environ.get("FOCUS_RELAY_AUDIO_BACKEND") == "null":      # pruebas sin tarjeta de sonido
            backends = [miniaudio.Backend.NULL]
        return miniaudio.PlaybackDevice(output_format=miniaudio.SampleFormat.SIGNED16, nchannels=2,
                                        sample_rate=RATE, backends=backends)

    def play(self, preset_id, volume):
        """Empieza a sonar `preset_id`. Devuelve True si arrancó."""
        with self._lock:
            self._stop_locked()
            self._volume = volume
            self.error = ""
            if preset_id not in CATALOG or CATALOG[preset_id][1] == "none":
                return False
            if not AVAILABLE:
                self.error = "miniaudio"
                return False
            kind, url = CATALOG[preset_id][1], CATALOG[preset_id][2]
            self._stop = threading.Event()
            try:
                dev = self._new_device()
                gen = self._noise_gen(kind) if kind != "stream" else self._stream_gen(url)
                next(gen)
                dev.start(gen)
            except Exception as exc:
                self.error = str(exc)[:120]
                self._stop.set()
                return False
            self._device = dev
            self.current = preset_id
            return True

    def _noise_gen(self, kind):
        stop = self._stop
        state = {"vol": None, "buf": None}
        pos = 0
        required = yield b""
        while not stop.is_set():
            if state["vol"] != self._volume:
                state["vol"], state["buf"] = self._volume, _noise_buffer(kind, self._volume)
            buf = state["buf"]
            need = required * 2
            chunk = array("h")
            while len(chunk) < need:
                take = min(need - len(chunk), len(buf) - pos)
                chunk.extend(buf[pos:pos + take])
                pos = (pos + take) % len(buf)
            required = yield chunk
        return

    def _stream_gen(self, url):
        stop = self._stop
        src = _HttpSource(url, stop)
        stream = miniaudio.stream_any(src, miniaudio.FileFormat.MP3,
                                      output_format=miniaudio.SampleFormat.SIGNED16,
                                      nchannels=2, sample_rate=RATE)
        required = yield b""
        try:
            while not stop.is_set():
                try:
                    chunk = stream.send(required)
                except StopIteration:
                    return
                v = self._volume
                if v < 0.999:
                    chunk = array("h", (int(x * v) for x in chunk))
                required = yield chunk
        finally:
            src.close()

    def set_volume(self, volume):
        self._volume = max(0.0, min(1.0, volume))

    def stop(self):
        with self._lock:
            self._stop_locked()

    def _stop_locked(self):
        self._stop.set()
        dev, self._device = self._device, None
        if dev is not None:
            try:
                dev.stop()
                dev.close()
            except Exception:
                pass
        self.current = ""
