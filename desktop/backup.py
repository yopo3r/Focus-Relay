"""Respaldo y restauración de los datos de la app (un .zip con los JSON de la carpeta de configuración).

* El respaldo NO incluye el enlace secreto del calendario (calendar_url): al restaurar se conserva el
  que ya tenga el equipo.
* Al restaurar solo se aceptan los archivos conocidos, se validan como JSON y los actuales se guardan
  antes con extensión .bak, así que una restauración equivocada se puede deshacer.
"""
import json
import os
import zipfile
from datetime import datetime

import config

FILES = ("config.json", "data.json", "tasks.json", "local_sessions.json", "calendar.ics")
MAX_MEMBER = 20 * 1024 * 1024
MANIFEST = "backup_info.json"


def default_name():
    return f"focus-relay-backup-{datetime.now():%Y%m%d-%H%M}.zip"


def export_zip(dest):
    """Crea el respaldo en `dest`. Devuelve la lista de archivos incluidos."""
    base = config.config_dir()
    included = []
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            p = os.path.join(base, name)
            if not os.path.isfile(p):
                continue
            if name == "config.json":
                cfg = config.load_config()
                cfg["calendar_url"] = ""                       # secreto: nunca sale en un respaldo
                z.writestr(name, json.dumps(cfg, ensure_ascii=False, indent=2))
            else:
                z.write(p, name)
            included.append(name)
        z.writestr(MANIFEST, json.dumps({"app_version": config.APP_VERSION,
                                         "created": datetime.now().isoformat(timespec="seconds"),
                                         "files": included}))
    return included


def inspect(src):
    """Valida un respaldo sin tocar nada. Devuelve {nombre: bytes} o lanza ValueError."""
    try:
        z = zipfile.ZipFile(src)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("No es un archivo de respaldo válido.") from exc
    out = {}
    with z:
        for info in z.infolist():
            if info.filename not in FILES:
                continue
            if info.file_size > MAX_MEMBER:
                raise ValueError("El respaldo contiene un archivo demasiado grande.")
            with z.open(info) as member:                       # tope real de lectura: el tamaño declarado puede mentir
                raw = member.read(MAX_MEMBER + 1)
            if len(raw) > MAX_MEMBER:
                raise ValueError("El respaldo contiene un archivo demasiado grande.")
            out[info.filename] = raw
    if not out:
        raise ValueError("El archivo no contiene datos de Focus Relay.")
    for name, raw in out.items():
        if name.endswith(".json"):
            try:
                data = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError(f"{name} está dañado.") from exc
            if name in ("config.json", "data.json") and not isinstance(data, dict):
                raise ValueError(f"{name} tiene un formato inesperado.")
            if name == "tasks.json" and not isinstance(data, dict):
                raise ValueError("tasks.json tiene un formato inesperado.")
            if name == "local_sessions.json" and not isinstance(data, list):
                raise ValueError("local_sessions.json tiene un formato inesperado.")
    return out


def restore_zip(src):
    """Restaura el respaldo. Devuelve los nombres restaurados."""
    members = inspect(src)
    base = config.config_dir()
    keep = config.load_config()
    for name, raw in members.items():
        if name == "config.json":
            new = json.loads(raw.decode("utf-8"))
            for k in ("calendar_url", "esp_url"):              # ajustes de este equipo: se conservan
                if k == "calendar_url" or keep.get(k):
                    new[k] = keep.get(k, "")
            raw = json.dumps(new, ensure_ascii=False, indent=2).encode("utf-8")
        p = os.path.join(base, name)
        if os.path.exists(p):
            os.replace(p, p + ".bak")
        tmp = p + ".tmp"
        with open(tmp, "wb") as f:
            f.write(raw)
        os.replace(tmp, p)
    try:                                                         # el motor local guarda el historial en memoria
        import local_timer
        local_timer.ENGINE._log = None
    except Exception:
        pass
    return sorted(members)


def erase_all():
    """Borra todos los datos de la app en esta carpeta (derecho de supresión): ajustes, sesiones, tareas, premios,
    calendario, cachés, respaldos .bak y el informe de bloqueos. No toca `app.lock` (lo usa la app abierta).
    Devuelve la cantidad de archivos borrados."""
    base = config.config_dir()
    n = 0
    for name in os.listdir(base):
        p = os.path.join(base, name)
        if name == "app.lock" or not os.path.isfile(p) or os.path.islink(p):
            continue
        try:
            os.remove(p)
            n += 1
        except OSError:
            pass
    return n
