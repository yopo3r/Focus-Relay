"""Manejo de configuración persistente para Focus Relay Desktop.

La configuración vive en un JSON dentro de la carpeta de configuración
del usuario (equivalente a %APPDATA% en Windows o ~/.config en Linux),
para que sobreviva reinicios y no dependa de dónde se ejecute el script.
"""
import copy
import json
import os
import platform
import threading

APP_DIR_NAME = "FocusRelayDesktop"
APP_VERSION = "3.27.0"
CONFIG_FILE_NAME = "config.json"

DEFAULT_CONFIG = {
    "esp_url": "http://192.168.1.50",
    "connection_mode": "device",   # "device" (con ESP-01S) | "local" (solo en la app, sin dispositivo)
    "local_durations": {"minutos": 25, "pomTrabajo": 25, "pomDescanso": 5, "pomDescansoLargo": 15, "pomCiclos": 4},
    "tutorial_done": False,        # el tutorial de bienvenida se muestra una sola vez
    "schema_version": 2,           # versión del formato de config.json (ver migrate)
    "goal_daily_min": 0,           # meta de enfoque por día en minutos (0 = sin meta)
    "goal_weekly_min": 0,          # meta semanal en minutos (0 = sin meta)
    "warn_end_min": 5,             # avisar cuando falten N minutos para terminar un bloque (0 = no avisar)
    "text_scale": 1.0,             # tamaño de los textos (0.9 / 1.0 / 1.15 / 1.3)
    "mascot_size": 110,            # tamaño de la mascota en píxeles (56–240)
    "mascot_x": None,              # posición en pantalla (None = esquina inferior derecha)
    "mascot_y": None,
    "eco_mode": False,             # equipos lentos: menos animación y sondeos más espaciados
    "streak_days": [0, 1, 2, 3, 4, 5, 6],   # días que cuentan para la racha (0 = lunes); los demás ni suman ni cortan
    "startup_tasks": False,        # al iniciar con el sistema (--background) abre el Panel en Tareas
    "mascot_color": "peach",       # paleta del cuerpo (ver mascot.PALETTES)
    "mascot_font": 10,            # tamaño de letra del globo (pt)
    "mascot_bye": True,            # la mascota se despide al cerrar la app
    "mascot_text": True,           # muestra los globos de texto
    "mascot_on_top": True,         # se mantiene por encima de las demás aplicaciones
    "mascot": True,                # mascota «Brote» en la esquina inferior de la ventana (opcional)
    "confetti": True,              # confeti al terminar una sesión de enfoque
    "confirm_quit": True,          # pedir confirmación simple al cerrar la app con una sesión en marcha (sin modo estricto)
    "confirm_stop": True,          # pedir confirmación al terminar una sesión antes de tiempo
    "strict_mode": False,          # modo estricto: terminar una sesión antes de tiempo exige confirmar varias veces
    "minimize_on_session": False,  # lo mismo al iniciar cualquier sesión (botón Iniciar, +5 min)
    "minimize_on_task": False,     # minimizar la app y avisar con una notificación al iniciar una tarea
    "strict_confirms": 3,          # cuántas confirmaciones seguidas (1 a 100)
    "block_in_timer": True,        # modo app: el bloqueo también actúa durante el Temporizador (no solo el Pomodoro)
    "next_activity": "",           # etiqueta o tarea que llevarán las próximas sesiones (se elige en el Panel)
    "strict_code_mixed": False,    # los códigos aleatorios mezclan mayúsculas y minúsculas (y se comparan distinguiéndolas)
    "strict_stop_code": False,     # modo estricto: además de las confirmaciones, escribir un código aleatorio para terminar antes
    "block_in_chrono": False,      # el bloqueo también actúa durante el Cronómetro
    "enabled": True,
    "poll_interval_ms": 1500,      # cada cuánto se consulta /estado del ESP
    "enforce_interval_ms": 1000,   # cada cuánto se revisan los procesos
    # "strict"          -> cierra cualquier app bloqueada apenas se detecta
    # "warn"            -> avisa y da un tiempo de gracia antes de cerrar
    # "prevent_launch"  -> no toca lo que ya estaba abierto; solo cierra
    #                      apps bloqueadas que se abran DESPUÉS de iniciar
    #                      la sesión de estudio
    "mode": "warn",
    "grace_seconds": 10,
    "blocked_apps": [],
    "blocked_sites": ["youtube.com", "facebook.com", "instagram.com", "x.com", "reddit.com"],   # sitios que bloquea la extensión del navegador
    "allowed_sites": [],           # excepciones (se permiten aunque estén en la lista anterior)
    "theme": "system",             # apariencia: "light" | "dark" | "system"
    "palette": "yopo",             # tema de color ("yopo" o id de themes_data.json / personalizado)
    "custom_themes": [],           # temas .theme importados por el usuario
    # --- Calendario y sesiones sugeridas ---
    "calendar_name": "",           # nombre del .ics importado (la copia vive en config_dir)
    "day_start": 8,                # horario de estudio: desde esta hora...
    "day_end": 22,                 # ...hasta esta hora
    "horizon_days": 7,             # cuántos días hacia adelante recomendar
    "max_sessions_per_day": 4,
    "calendar_url": "",            # enlace iCal (suscripción). Es secreto: no se muestra ni se registra
    "calendar_refresh_minutes": 60,
    "planned_sessions": [],        # sesiones sugeridas que el usuario agregó a su agenda
    "manual_events": [],           # controles/entregas agregados a mano (ver manual_events.py)
    # --- Panel (lo que antes vivía en la página web del ESP-01S) ---
    "language": "es",              # es | en | fr | pt | de | it | nl | ru | ja | ko | zh  (el OLED solo tiene es/en/fr/pt/zh; en los demás muestra inglés)
    "user_name": "",
    "mode_colors": {"T": "#5b5bd6", "C": "#059669", "P": "#dc2626"},
    "tags": [],                    # etiquetas de actividad (antes en el ESP)
    "phrases": [],                 # frases motivacionales propias (antes en el ESP)
    "legacy_imported": False,      # ya se importaron etiquetas/frases del firmware antiguo
    # --- Música ---
    "music_auto_start": True,
    "music_auto_stop": True,
    "music_volume": 0.35,
    "music_by_mode": {"T": "brown", "C": "groove", "W": "drone", "D": "space"},
    "bridge_port": 8765,           # puerto del puente con la extensión (avanzado; la extensión debe usar el mismo)
    "bridge": True,                # la extensión del navegador puede seguir esta app (127.0.0.1, solo lectura)
    "adaptive": True,              # adaptar sugerencias, metas y consejos a mi uso (todo local)
    "sound_end": True,             # sonido suave al terminar una sesión o cambiar de modo (Pomodoro)
    "sound_volume": 0.6,
    # --- Premios ---
    "reward_categories": ["trenes", "autos", "animales"],
}

# Datos que cambian solos (los escribe el hilo de fondo): van en un archivo aparte
# para no pisar la configuración que el usuario edita en las ventanas.
DEFAULT_DATA = {"rewards": [], "last_completion_token": "", "rewarded": [], "achievements": {}, "ach_init": False}


def config_dir():
    """Retorna (y crea si no existe) la carpeta donde vive config.json."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config"
        )
    path = os.path.join(base, APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    if system != "Windows":
        try:
            os.chmod(path, 0o700)            # los datos (sesiones, tareas, calendario) son solo del usuario
        except OSError:
            pass
    return path


def config_path():
    return os.path.join(config_dir(), CONFIG_FILE_NAME)


def calendar_path():
    """Copia local del calendario importado (nunca sale del computador)."""
    return os.path.join(config_dir(), "calendar.ics")


_load_cache = {"key": None, "cfg": None}


def load_config():
    """Lee la configuración. Se llama muchas veces por segundo (sondeo, Panel, mascota): si el archivo no cambió se
    reutiliza la lectura anterior (una copia, para que quien la modifique no altere la caché)."""
    path = config_path()
    try:
        st = os.stat(path)
        key = (path, st.st_mtime_ns, st.st_size)
    except OSError:
        key = None
    if key is not None and key == _load_cache["key"]:
        return copy.deepcopy(_load_cache["cfg"])
    if not os.path.exists(path):
        save_config(DEFAULT_CONFIG)
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return copy.deepcopy(DEFAULT_CONFIG)
    merged = copy.deepcopy(DEFAULT_CONFIG)
    merged.update(data if isinstance(data, dict) else {})
    result = migrate(_coerce_types(merged, DEFAULT_CONFIG))
    if key is not None:
        _load_cache["key"], _load_cache["cfg"] = key, copy.deepcopy(result)
    return result


SCHEMA_VERSION = 2


def _coerce_types(values, defaults):
    """Un archivo editado a mano o corrupto puede traer tipos equivocados (p. ej. una lista donde va un texto):
    cada clave cuyo tipo no coincide con el del valor por defecto vuelve a ese valor."""
    for key, default in defaults.items():
        if key not in values or default is None:
            continue
        val = values[key]
        if isinstance(default, bool):
            ok = isinstance(val, bool)
        elif isinstance(default, (int, float)):
            ok = isinstance(val, (int, float)) and not isinstance(val, bool)
        else:
            ok = isinstance(val, type(default))
        if not ok:
            values[key] = copy.deepcopy(default)
    return values


def migrate(cfg):
    """Lleva una configuración antigua al formato actual (sin tocar lo que el usuario ya eligió)."""
    # v2 añadió metas y aviso previo: load_config ya completa las claves nuevas con sus valores por defecto
    # valores fuera de rango o de tipo incorrecto (archivo editado a mano) vuelven al valor por defecto
    for k, (lo, hi) in {"goal_daily_min": (0, 1440), "goal_weekly_min": (0, 10080), "warn_end_min": (0, 60)}.items():
        try:
            cfg[k] = max(lo, min(hi, int(cfg.get(k, DEFAULT_CONFIG[k]))))
        except (TypeError, ValueError):
            cfg[k] = DEFAULT_CONFIG[k]
    try:
        cfg["bridge_port"] = max(1024, min(65535, int(cfg.get("bridge_port", 8765))))
    except (TypeError, ValueError):
        cfg["bridge_port"] = 8765
    try:
        cfg["strict_confirms"] = max(1, min(100, int(cfg.get("strict_confirms", 3))))
    except (TypeError, ValueError):
        cfg["strict_confirms"] = 3
    try:
        cfg["text_scale"] = min(1.6, max(0.8, float(cfg.get("text_scale", 1.0))))
    except (TypeError, ValueError):
        cfg["text_scale"] = 1.0
    cfg["schema_version"] = SCHEMA_VERSION
    return cfg


_cfg_lock = threading.RLock()


def update_config(**changes):
    """Lee, cambia y guarda la configuración bajo el mismo candado (para quien escribe desde otro hilo o ventana)."""
    with _cfg_lock:
        cfg = load_config()
        cfg.update(changes)
        save_config(cfg)
        return cfg


def save_config(cfg):
    """Escritura atómica; el candado evita que dos hilos (interfaz, sondeo, puente) pisen el mismo archivo temporal."""
    path = config_path()
    with _cfg_lock:
        tmp_path = f"{path}.{os.getpid()}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(tmp_path, 0o600)  # puede contener el enlace secreto del calendario
        except OSError:
            pass
        os.replace(tmp_path, path)


# --- Datos de fondo (premios, etc.) -----------------------------------------
_data_lock = threading.Lock()


def data_path():
    return os.path.join(config_dir(), "data.json")


def load_data():
    with _data_lock:
        try:
            with open(data_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
    merged = copy.deepcopy(DEFAULT_DATA)
    merged.update(data if isinstance(data, dict) else {})
    return _coerce_types(merged, DEFAULT_DATA)


def save_data(data):
    with _data_lock:
        tmp = data_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, data_path())


def system_env():
    """Entorno para lanzar programas del sistema (notify-send, xdg-open...). En el binario de Linux empaquetado
    PyInstaller antepone sus bibliotecas a LD_LIBRARY_PATH y rompería esos programas: se restaura el valor original."""
    env = dict(os.environ)
    if getattr(__import__("sys"), "frozen", False):
        orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if orig is not None:
            env["LD_LIBRARY_PATH"] = orig
        else:
            env.pop("LD_LIBRARY_PATH", None)
    return env
