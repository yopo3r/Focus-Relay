"""Sonidos suaves de aviso: fin de sesión y cambio de modo del Pomodoro.

Se sintetizan en el propio computador (campanillas con armónicos que se apagan solas y un eco muy
tenue), sin archivos de audio. Se reproducen con `miniaudio`, igual que la música; si no está
instalado o no hay tarjeta de sonido, simplemente no suenan.
"""
import math
import os
import threading
import time
from array import array

try:
    import miniaudio
    AVAILABLE = True
except Exception:                       # pragma: no cover - depende del entorno
    miniaudio = None
    AVAILABLE = False

RATE = 44100

# Notas (Hz) de la escala de Do mayor: suenan consonantes y relajadas.
C5, D5, E5, G5, A5, C6 = 523.25, 587.33, 659.25, 783.99, 880.00, 1046.50

# tipo -> lista de (nota, segundos desde el inicio)
MELODIES = {
    "done": [(C5, 0.00), (E5, 0.16), (G5, 0.32), (C6, 0.48)],     # arpegio ascendente: ¡terminaste!
    "break": [(G5, 0.00), (E5, 0.22), (C5, 0.44)],                # descendente y calmado: toca descansar
    "focus": [(E5, 0.00), (A5, 0.20)],                            # ascendente y luminoso: vuelta al trabajo
}
KINDS = tuple(MELODIES)
TAIL = 1.6                                                        # segundos que dura la última nota al apagarse


def _bell(freq, length):
    """Una campanilla: fundamental + armónicos que decaen más rápido cuanto más agudos."""
    n = int(RATE * length)
    out = [0.0] * n
    partials = ((1.0, 1.0, 0.70), (2.0, 0.32, 0.38), (3.0, 0.12, 0.22), (4.2, 0.05, 0.12))   # (múltiplo, nivel, constante de decaimiento s)
    for mult, level, tau in partials:
        w = 2 * math.pi * freq * mult / RATE
        for i in range(n):
            tt = i / RATE
            out[i] += level * math.sin(w * i) * math.exp(-tt / tau) * min(1.0, tt / 0.008)   # ataque de 8 ms: sin chasquido
    return out


def synth(kind):
    """Devuelve el sonido como lista de muestras mono en [-1, 1] (sin volumen aplicado)."""
    notes = MELODIES.get(kind) or MELODIES["done"]
    total = int(RATE * (notes[-1][1] + TAIL))
    dry = [0.0] * total
    for freq, start in notes:
        bell = _bell(freq, TAIL)
        base = int(RATE * start)
        for i, v in enumerate(bell):
            if base + i < total:
                dry[base + i] += v
    mix = list(dry)                                               # eco tenue: da sensación de espacio
    for delay, gain in ((0.19, 0.22), (0.38, 0.10)):
        d = int(RATE * delay)
        for i in range(d, total):
            mix[i] += dry[i - d] * gain
    peak = max(1e-9, max(abs(v) for v in mix))
    fade = int(RATE * 0.25)                                       # cierre suave
    for i in range(fade):
        mix[total - 1 - i] *= i / fade
    return [v / peak for v in mix]


_cache = {}


def samples(kind, volume):
    """Buffer estéreo int16 listo para reproducir (la síntesis se guarda en memoria)."""
    if kind not in _cache:
        _cache[kind] = synth(kind)
    gain = max(0.0, min(1.0, volume)) * 0.8 * 32767
    out = array("h", bytes(len(_cache[kind]) * 4))
    for i, v in enumerate(_cache[kind]):
        s = int(v * gain)
        out[2 * i] = s
        out[2 * i + 1] = s
    return out


def _generator(buf):
    pos = 0
    required = yield b""
    while pos < len(buf):
        need = required * 2
        chunk = buf[pos:pos + need]
        pos += need
        if len(chunk) < need:
            chunk = chunk + array("h", bytes((need - len(chunk)) * 2))
        required = yield chunk


def _play_blocking(kind, volume):
    backends = [miniaudio.Backend.NULL] if os.environ.get("FOCUS_RELAY_AUDIO_BACKEND") == "null" else None
    buf = samples(kind, volume)
    dev = miniaudio.PlaybackDevice(output_format=miniaudio.SampleFormat.SIGNED16, nchannels=2,
                                   sample_rate=RATE, backends=backends)
    try:
        gen = _generator(buf)
        next(gen)
        dev.start(gen)
        time.sleep(len(buf) / 2 / RATE + 0.4)
    finally:
        try:
            dev.stop()
            dev.close()
        except Exception:
            pass


def play(kind, volume=0.6):
    """Suena en un hilo aparte (no frena la app ni corta la música). False si no hay audio disponible."""
    if not AVAILABLE or volume <= 0:
        return False

    def run():
        try:
            _play_blocking(kind, volume)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()
    return True
