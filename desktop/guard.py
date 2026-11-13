"""Reglas para terminar una sesión antes de tiempo (sin interfaz, para poder probarlas)."""

import re
import secrets

MIN_CONFIRMS, MAX_CONFIRMS = 1, 100
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"        # sin 0/O ni 1/I/L, que se confunden al leer


def session_at_risk(est):
    """True si terminar ahora cortaría una sesión de enfoque: Temporizador o fase de trabajo del Pomodoro."""
    return bool(est and est.get("ejecutando") and (est.get("modo") == "T" or (est.get("modo") == "P" and est.get("fase") == "W")))


def clamp_confirms(value, default=3):
    try:
        return max(MIN_CONFIRMS, min(MAX_CONFIRMS, int(str(value).strip())))
    except (TypeError, ValueError):
        return default


def confirmations_needed(cfg, est):
    """Cuántas veces seguidas hay que confirmar para terminar: 0 = sin aviso, 1 = aviso simple, N = modo estricto."""
    if not session_at_risk(est):
        return 0
    if cfg.get("strict_mode"):
        return clamp_confirms(cfg.get("strict_confirms", 3))
    return 1 if cfg.get("confirm_stop", True) else 0


def settings_locked(cfg, est):
    """Con el modo estricto activo y un Temporizador o Pomodoro en marcha (también en descanso), el modo estricto
    no se puede cambiar ni desactivar."""
    return bool(cfg.get("strict_mode") and est and est.get("ejecutando") and est.get("modo") in ("T", "P"))


def block_settings_locked(est, cfg=None):
    """El bloqueo de apps (lista, intensidad, activación) no se puede cambiar mientras hay un Temporizador o Pomodoro
    en marcha (también en descanso), para no soltarlo en pleno enfoque. El Cronómetro cuenta solo si el bloqueo
    también actúa durante él (`block_in_chrono`)."""
    if not (est and est.get("ejecutando")):
        return False
    if est.get("modo") == "C":
        return bool(cfg and cfg.get("block_in_chrono"))
    return est.get("modo") in ("T", "P")


def quit_locked(cfg, est):
    """Con el modo estricto activo y cualquier sesión en marcha (también el Cronómetro), cerrar la app exige
    escribir un código."""
    return bool(cfg.get("strict_mode") and est and est.get("ejecutando"))


# Con «mayúsculas y minúsculas»: solo letras cuyas dos formas se distinguen bien a simple vista (sin K/k, S/s, V/v…)
MIXED_UPPER, MIXED_LOWER, MIXED_DIGITS = "ABDEFGHMNQRT", "abdefghmnqrt", "23456789"


def quit_needs_confirm(cfg, est):
    """Sin modo estricto: si hay una sesión en marcha y la opción está activa, cerrar la app pide una confirmación simple."""
    return bool(cfg.get("confirm_quit", True) and est and est.get("ejecutando"))


def new_code(groups=2, size=4, mixed=False):
    """Código aleatorio (p. ej. «K7QM-4TXD») que hay que escribir para desactivar el modo estricto; distinto cada vez.
    Con `mixed` mezcla mayúsculas y minúsculas (p. ej. «Ab7Q-dT4h»), con al menos una de cada una."""
    if not mixed:
        return "-".join("".join(secrets.choice(CODE_ALPHABET) for _ in range(size)) for _ in range(groups))
    alphabet = MIXED_UPPER + MIXED_LOWER + MIXED_DIGITS
    while True:
        raw = "".join(secrets.choice(alphabet) for _ in range(groups * size))
        if any(c in MIXED_UPPER for c in raw) and any(c in MIXED_LOWER for c in raw):
            return "-".join(raw[i:i + size] for i in range(0, len(raw), size))


def code_matches(expected, typed, case_sensitive=False):
    """Compara sin importar guiones ni espacios (y, salvo `case_sensitive`, tampoco mayúsculas)."""
    norm = lambda x: re.sub(r"[\s-]", "", str(x or ""))
    a, b = norm(expected), norm(typed)
    if not case_sensitive:
        a, b = a.upper(), b.upper()
    return bool(a) and a == b


def code_mixed(cfg):
    return bool((cfg or {}).get("strict_code_mixed", False))
