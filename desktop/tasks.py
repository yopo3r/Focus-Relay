"""Lista de tareas del día (funciones puras + persistencia en tasks.json).

* Cada tarea pertenece a un día. Las tareas manuales sin terminar de días anteriores se pasan
  automáticamente a hoy ("arrastre"), así nada se pierde.
* Las tareas automáticas (plantillas) se crean solas los días de la semana elegidos (0 = lunes).
* Lo ya completado queda como historial para las estadísticas.
"""
import json
import os
import threading
import uuid
from datetime import date, timedelta

from config import config_dir

_lock = threading.RLock()
KEEP_DAYS = 800
MAX_TEXT = 120


def path():
    return os.path.join(config_dir(), "tasks.json")


def empty():
    return {"items": [], "templates": [], "last_roll": ""}


def load():
    with _lock:
        try:
            with open(path(), encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return empty()
            base = empty()
            base.update({k: data.get(k, base[k]) for k in base})
            # un archivo editado a mano o dañado nunca debe romper la app: se descartan entradas inválidas
            base["items"] = [i for i in base["items"] if isinstance(i, dict) and {"id", "text", "date"} <= set(i)] \
                if isinstance(base["items"], list) else []
            for it in base["items"]:                         # campos opcionales ausentes: valores por defecto
                it.setdefault("done", False)
                it.setdefault("done_on", None)
                it.setdefault("auto", None)
            base["templates"] = [i for i in base["templates"]
                                 if isinstance(i, dict) and {"id", "text", "days"} <= set(i) and isinstance(i["days"], list)] \
                if isinstance(base["templates"], list) else []
            if not isinstance(base["last_roll"], str):
                base["last_roll"] = ""
            return base
        except (OSError, ValueError):
            return empty()


def save(data):
    with _lock:
        p = path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, p)


def _clean(text):
    return " ".join(str(text).split())[:MAX_TEXT]


def roll(data, today=None):
    """Pone al día la lista para `today`: arrastra pendientes y crea las tareas automáticas. True si cambió."""
    today = today or date.today()
    iso = today.isoformat()
    changed = False
    for it in data["items"]:
        if not it["done"] and not it.get("auto") and it["date"] < iso:
            it["carried_from"] = it.get("carried_from") or it["date"]
            it["date"] = iso
            changed = True
    have = {(it.get("auto"), it["date"]) for it in data["items"] if it.get("auto")}
    for tpl in data["templates"]:
        if tpl.get("active", True) and today.weekday() in tpl.get("days", []) and (tpl["id"], iso) not in have:
            data["items"].append({"id": uuid.uuid4().hex[:10], "text": tpl["text"], "date": iso,
                                  "done": False, "done_on": None, "auto": tpl["id"]})
            changed = True
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    kept = [it for it in data["items"] if it["date"] >= cutoff]
    if len(kept) != len(data["items"]):
        data["items"], changed = kept, True
    if data.get("last_roll") != iso:
        data["last_roll"], changed = iso, True
    return changed


def today_items(data, today=None):
    iso = (today or date.today()).isoformat()
    items = [it for it in data["items"] if it["date"] == iso]
    return sorted(items, key=lambda it: it["done"])       # pendientes arriba (orden estable)


def add_task(data, text, day=None):
    text = _clean(text)
    if not text:
        return None
    item = {"id": uuid.uuid4().hex[:10], "text": text, "date": (day or date.today()).isoformat(),
            "done": False, "done_on": None, "auto": None}
    data["items"].append(item)
    return item


def set_done(data, item_id, done, today=None):
    for it in data["items"]:
        if it["id"] == item_id:
            it["done"] = bool(done)
            it["done_on"] = (today or date.today()).isoformat() if done else None
            return True
    return False


def delete_task(data, item_id):
    n = len(data["items"])
    data["items"] = [it for it in data["items"] if it["id"] != item_id]
    return len(data["items"]) != n


def add_template(data, text, days):
    text = _clean(text)
    days = sorted({int(d) for d in days if 0 <= int(d) <= 6})
    if not text or not days:
        return None
    tpl = {"id": uuid.uuid4().hex[:10], "text": text, "days": days, "active": True}
    data["templates"].append(tpl)
    return tpl


def delete_template(data, tpl_id, remove_today=True, today=None):
    """Quita la plantilla; sus tareas de hoy aún sin hacer también (las ya hechas se conservan)."""
    data["templates"] = [t for t in data["templates"] if t["id"] != tpl_id]
    if remove_today:
        iso = (today or date.today()).isoformat()
        data["items"] = [it for it in data["items"]
                         if not (it.get("auto") == tpl_id and it["date"] >= iso and not it["done"])]


def toggle_template_day(data, tpl_id, weekday):
    for t in data["templates"]:
        if t["id"] == tpl_id:
            days = set(t["days"])
            days.symmetric_difference_update({weekday})
            t["days"] = sorted(days)
            return t["days"]
    return None


def done_by_date(data):
    """{date: tareas completadas ese día} (día en que se marcaron)."""
    out = {}
    for it in data["items"]:
        if it["done"]:
            try:
                d = date.fromisoformat(it.get("done_on") or it["date"])
            except ValueError:
                continue
            out[d] = out.get(d, 0) + 1
    return out


def progress(data, today=None):
    items = [it for it in data["items"] if it["date"] == (today or date.today()).isoformat()]
    return sum(1 for it in items if it["done"]), len(items)
