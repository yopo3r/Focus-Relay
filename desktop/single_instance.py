"""Evita que se abran dos copias de la app (dos copias escribirían los mismos archivos y cerrarían apps por duplicado)."""
import os
import sys

_handle = None          # se mantiene abierto mientras viva el proceso; el sistema libera el candado al terminar


def acquire(directory):
    """True si esta es la única instancia. Si no se puede comprobar (permisos, etc.) se permite arrancar."""
    global _handle
    try:
        os.makedirs(directory, exist_ok=True)
        fh = open(os.path.join(directory, "app.lock"), "a+")
    except OSError:
        return True
    try:
        if sys.platform.startswith("win"):
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return False
    except ImportError:
        pass
    _handle = fh
    return True
