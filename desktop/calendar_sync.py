"""Suscripción a un calendario por enlace (iCal/.ics) con actualización automática.

Funciona con la "dirección secreta en formato iCal" de Google Calendar, el
enlace ICS de un calendario publicado en Outlook y cualquier URL .ics.

Notas de seguridad:
- El enlace es una credencial: da acceso de lectura a tu calendario. Se guarda
  solo en config.json (permisos 600 donde el sistema lo permite) y NUNCA se
  escribe en mensajes de error, logs ni en pantalla.
- Solo se aceptan http(s) y webcal. Se ignoran file://, ftp://, etc.
- Si una descarga falla o no es un calendario válido, se conserva la última
  copia buena.
"""
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from config import calendar_path, load_config

MAX_BYTES = 10 * 1024 * 1024
STATE = {"last_ok": None, "last_error": None, "last_attempt": 0.0}
_lock = threading.Lock()
_sync_lock = threading.Lock()   # evita descargas simultáneas


class SyncError(Exception):
    """Error con un mensaje apto para mostrar al usuario (sin incluir el enlace)."""


def normalize_url(url):
    url = (url or "").strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        raise SyncError("El enlace debe empezar con https:// o webcal://")
    return url


def _decode(raw):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def fetch_ics(url, timeout=15):
    """Descarga y valida el calendario. Devuelve el texto o lanza SyncError."""
    url = normalize_url(url)
    req = urllib.request.Request(
        url, headers={"User-Agent": "FocusRelayDesktop/1.0", "Accept": "text/calendar, */*"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise SyncError(
            f"El servidor respondió HTTP {exc.code}. ¿El enlace expiró o fue restablecido?"
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise SyncError("No se pudo descargar el calendario. Revisa tu conexión a internet.") from None
    if len(raw) > MAX_BYTES:
        raise SyncError("El calendario es demasiado grande (más de 10 MB).")
    text = _decode(raw)
    if "BEGIN:VCALENDAR" not in text.upper():
        raise SyncError(
            "El enlace no devolvió un calendario válido. Usa la dirección en formato iCal (.ics)."
        )
    return text


def sync_now(url=None):
    """Descarga el calendario y lo guarda. Devuelve (ok, mensaje, cambió)."""
    with _sync_lock:
        if url is None:
            url = load_config().get("calendar_url", "")
        with _lock:
            STATE["last_attempt"] = time.time()
        try:
            text = fetch_ics(url)
        except SyncError as exc:
            with _lock:
                STATE["last_error"] = str(exc)
            return False, str(exc), False
        path = calendar_path()
        changed = True
        try:
            with open(path, "r", encoding="utf-8", newline="") as f:
                changed = f.read() != text
        except OSError:
            pass
        if changed:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            os.replace(tmp, path)
        with _lock:
            STATE["last_ok"] = time.time()
            STATE["last_error"] = None
        return True, "Calendario actualizado.", changed


def status():
    with _lock:
        return dict(STATE)


def start_background(stop_event, check_every=30):
    """Hilo que mantiene el calendario al día mientras la app esté abierta."""

    def loop():
        while not stop_event.is_set():
            try:
                cfg = load_config()
                url = (cfg.get("calendar_url") or "").strip()
                if url:
                    every = max(15, int(cfg.get("calendar_refresh_minutes", 60))) * 60
                    with _lock:
                        due = time.time() - STATE["last_attempt"] >= every
                    if due:
                        sync_now(url)
            except Exception:
                pass  # el hilo de sincronización nunca debe tumbar la app
            stop_event.wait(check_every)

    t = threading.Thread(target=loop, name="calendar-sync", daemon=True)
    t.start()
    return t
