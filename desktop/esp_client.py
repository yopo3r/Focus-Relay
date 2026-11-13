"""Cliente HTTP mínimo para consultar /estado en el ESP-01S.

Usa únicamente la librería estándar (sin dependencias extra) y replica
el mismo endpoint y timeout que ya usa la extensión Focus Relay del
navegador, para que ambos "consumidores" vean exactamente el mismo
estado del temporizador.
"""
import json
import urllib.error
import urllib.parse
import urllib.request


LOCAL = "local://"      # "dirección" especial: el temporizador corre dentro de la app (sin ESP-01S)


def url_of(cfg):
    """Dirección efectiva según el modo de funcionamiento (dispositivo o solo app)."""
    return LOCAL if cfg.get("connection_mode") == "local" else cfg.get("esp_url", "")


def safe_base(esp_url):
    """Dirección base del dispositivo, o "" si no es una URL http(s) (evita file:// y otros esquemas)."""
    url = (esp_url or "").strip()
    if url and "://" not in url:
        url = "http://" + url                       # el usuario suele escribir solo la IP
    return url.rstrip("/") if urllib.parse.urlparse(url).scheme in ("http", "https") else ""


def _local():
    import local_timer
    return local_timer


def get_estado(esp_url, timeout=1.8):
    """Devuelve el dict de /estado, o None si el ESP no responde."""
    if esp_url == LOCAL:
        return _local().ENGINE.snapshot()
    if not esp_url:
        return None
    base = safe_base(esp_url)
    if not base:
        return None
    url = base + "/estado"
    try:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-store"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def fit_activity(name, max_bytes=24):
    """Acorta el nombre a `max_bytes` bytes UTF-8 (límite del firmware), por palabras si se puede."""
    name = " ".join(name.split())
    if len(name.encode("utf-8")) <= max_bytes:
        return name
    words = name.split(" ")
    while len(words) > 1 and len(" ".join(words).encode("utf-8")) > max_bytes:
        words.pop()
    out = " ".join(words)
    while len(out.encode("utf-8")) > max_bytes:
        out = out[:-1]
    return out.strip()


def start_current(esp_url, minutes, activity=""):
    """Inicia una sesión con una etiqueta. En el modo app respeta el modo actual (Temporizador, Cronómetro o
    Pomodoro); con dispositivo es un inicio rápido de `minutes` minutos. Devuelve el estado nuevo (o None)."""
    if esp_url == LOCAL:
        eng = _local().ENGINE
        if eng.snapshot()["ejecutando"]:
            return None
        eng.start(None if eng.mode != "T" else minutes, fit_activity(activity) if activity else "")
        return eng.snapshot()
    start_session(esp_url, minutes, activity)
    return None


def start_session(esp_url, minutes, activity="", timeout=4.0):
    """Inicia en el ESP una sesión de Temporizador de `minutes` minutos.

    Devuelve (estado, mensaje) con estado en:
      "ok"           -> el dispositivo confirmó la duración pedida
      "old_firmware" -> arrancó, pero con 5 min: el firmware no admite duración personalizada
      "busy"         -> ya hay una sesión en curso
      "error"        -> sin conexión o petición rechazada
    """
    if esp_url == LOCAL:
        eng = _local().ENGINE
        minutes = max(1, min(99, int(minutes)))
        if eng.snapshot()["ejecutando"]:
            return "busy", "Ya hay una sesión en curso."
        eng.set_mode("T")
        eng.start(minutes, fit_activity(activity) if activity else "")
        return "ok", f"Sesión de {minutes} min iniciada."
    if not esp_url:
        return "error", "Falta la dirección del ESP-01S."
    minutes = max(1, min(99, int(minutes)))
    data = {"minutos": str(minutes)}
    if activity:
        data["actividad"] = fit_activity(activity)
    if not safe_base(esp_url):
        return "error", "Falta la dirección del ESP-01S."
    body = urllib.parse.urlencode(data).encode("ascii")  # urlencode ya escapa el UTF-8
    req = urllib.request.Request(
        safe_base(esp_url) + "/inicio-rapido",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            return "busy", "El dispositivo ya tiene una sesión en curso."
        return "error", f"El dispositivo rechazó la petición (HTTP {exc.code})."
    except (urllib.error.URLError, TimeoutError, OSError):
        return "error", "No se pudo contactar al ESP-01S. Revisa la IP y que esté conectado al Wi-Fi."
    try:
        confirmed = json.loads(raw).get("minutos")
    except ValueError:
        confirmed = None
    if confirmed == minutes or (confirmed is None and minutes == 5):
        return "ok", f"Sesión de {minutes} min iniciada en el ESP-01S."
    return "old_firmware", (
        "Se inició una sesión de 5 minutos: el firmware instalado no admite duración "
        "personalizada. Actualiza el firmware para usar esta función."
    )


# =============================================================================
# API completa del dispositivo (lo que antes hacía la página web del ESP-01S)
# =============================================================================
import time as _time


def _call(esp_url, path, data=None, method=None, timeout=3.0):
    """Petición HTTP al ESP. Devuelve (status, texto) o (None, mensaje) si no hubo respuesta."""
    base = safe_base(esp_url)
    if not base:
        return None, "Falta la dirección del ESP-01S."
    body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        base + path, data=body,
        method=method or ("POST" if body is not None else "GET"),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-store"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, "No se pudo contactar al ESP-01S."


def _json(text, default=None):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default


def set_mode(esp_url, mode):
    """mode: 'T' | 'C' | 'P'. Devuelve el estado nuevo (dict) o None."""
    if esp_url == LOCAL:
        eng = _local().ENGINE
        return eng.snapshot() if eng.set_mode(mode) else None
    status, text = _call(esp_url, "/estado", {"modo": mode})
    return _json(text) if status == 200 else None


def toggle_run(esp_url, activity=""):
    """Equivale a pulsar START/STOP en el dispositivo. En el modo app, `activity` etiqueta la sesión que arranque."""
    if esp_url == LOCAL:
        return _local().ENGINE.toggle(fit_activity(activity) if activity else "") or True
    status, _ = _call(esp_url, "/control", {"accion": "toggle"})
    return status in (200, 202)


def extend_session(esp_url, seconds=300):
    if esp_url == LOCAL:
        return _local().ENGINE.extend(seconds)
    status, _ = _call(esp_url, "/ajustar", {"segundos": str(seconds)})
    return status in (200, 202)


# --- historial unificado -----------------------------------------------------------------------------
# Las sesiones hechas en el modo «solo app» (archivo local) y las del dispositivo conviven en una sola lista, así
# cambiar de modo no «pierde» nada. Las del dispositivo se guardan además en una caché local, para seguir viéndolas
# cuando no está conectado. Cada entrada lleva de dónde viene: "_src" ("app" | "device") y su índice en esa fuente
# ("_i"), que es lo que necesitan etiquetar y borrar.
SRC_APP, SRC_DEVICE = "app", "device"


def _cache_path():
    import os
    from config import config_dir
    return os.path.join(config_dir(), "device_log_cache.json")


def _read_cache():
    import json
    try:
        with open(_cache_path(), encoding="utf-8") as f:
            data = json.load(f)
        return [s for s in data if isinstance(s, dict)] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _write_cache(entries):
    import json
    import os
    path = _cache_path()
    try:
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass


def _annotate(entries, src):
    out = []
    for i, s in enumerate(entries):
        if isinstance(s, dict):
            d = dict(s)
            d["_src"], d["_i"] = src, i
            out.append(d)
    return out


def merge_logs(*lists):
    """Une varias listas de sesiones en orden cronológico (las sin fecha van primero, conservando su orden)."""
    allv = [s for lst in lists for s in lst]
    return sorted(allv, key=lambda s: s.get("epoch") or 0)


def get_log(esp_url):
    """Historial unificado de sesiones (app + dispositivo): lista de dicts {duracion_seg, modo, epoch?, actividad?,
    completada, _src, _i}. Con el dispositivo sin respuesta devuelve lo que hay guardado; None solo si no hay nada."""
    app = _annotate(_local().ENGINE.get_log(), SRC_APP)
    if esp_url == LOCAL:
        return merge_logs(app, _annotate(_read_cache(), SRC_DEVICE))
    status, text = _call(esp_url, "/datos", timeout=6.0)
    data = _json(text) if status == 200 else None
    if isinstance(data, list):
        _write_cache(data)
        return merge_logs(app, _annotate(data, SRC_DEVICE))
    cached = _read_cache()
    return merge_logs(app, _annotate(cached, SRC_DEVICE)) if (cached or app) else None


def clear_log(esp_url):
    """Borra el historial completo: el de la app, la caché del dispositivo y, si está conectado, el del dispositivo."""
    ok = _local().ENGINE.clear_log()
    _write_cache([])
    if esp_url != LOCAL:
        status, _ = _call(esp_url, "/borrar", {}, method="POST")
        ok = ok and status == 200
    return ok


def tag_entry(esp_url, entry, activity):
    """Etiqueta una sesión de la lista unificada, en la fuente de la que viene."""
    activity = fit_activity(activity)
    i = entry.get("_i")
    if i is None:
        return False
    if entry.get("_src") == SRC_APP:
        return _local().ENGINE.tag(int(i), activity)
    cache = _read_cache()                                    # sesión del dispositivo: se actualiza también la caché
    if 0 <= int(i) < len(cache):
        if activity:
            cache[int(i)]["actividad"] = activity
        else:
            cache[int(i)].pop("actividad", None)
        _write_cache(cache)
    if esp_url == LOCAL:
        return True                                          # sin conexión: queda en la caché
    status, _ = _call(esp_url, "/etiquetar", {"indice": str(i), "actividad": activity})
    return status == 200


def tag_session(esp_url, index, activity):
    """Etiqueta por índice dentro de UNA fuente (la local si el modo es «solo app», el dispositivo si no)."""
    if esp_url == LOCAL:
        return _local().ENGINE.tag(int(index), fit_activity(activity))
    status, _ = _call(esp_url, "/etiquetar", {"indice": str(index), "actividad": fit_activity(activity)})
    return status == 200


def sync_time(esp_url, epoch=None):
    """Le pasa la hora de este computador al ESP (no tiene reloj propio)."""
    if esp_url == LOCAL:
        return True
    status, _ = _call(esp_url, "/hora", {"epoch": str(int(epoch or _time.time()))})
    return status == 200


def get_device_config(esp_url):
    if esp_url == LOCAL:
        return _local().get_device_config()
    status, text = _call(esp_url, "/config")
    return _json(text) if status == 200 else None


def save_device_config(esp_url, values):
    if esp_url == LOCAL:
        return _local().save_device_config(values)
    status, _ = _call(esp_url, "/config", {k: str(v) for k, v in values.items()})
    return status == 200


def set_oled_language(esp_url, code):
    if esp_url == LOCAL:
        return True
    code = code if code in ("es", "en", "fr", "pt", "zh") else "en"     # el OLED solo tiene fuentes de esos idiomas
    status, _ = _call(esp_url, "/idioma", {"idioma": code})
    return status == 200


def get_legacy_list(esp_url, path):
    """Solo firmware antiguo: etiquetas (/actividades) o frases (/frases) guardadas en el ESP."""
    if esp_url == LOCAL:
        return None
    status, text = _call(esp_url, path)
    data = _json(text) if status == 200 else None
    return data if isinstance(data, list) else None
