"""Eventos agregados a mano (controles, entregas, clases sueltas).

Complementan al calendario importado: muchos calendarios solo traen el
horario de clases y los controles/entregas se anotan en otro lado. Se
guardan en config.json y se mezclan con el calendario al recomendar.
"""
import re
import uuid
from datetime import date, datetime, time, timedelta

from calendar_planner import DAYS_ES, Event

# clave -> (etiqueta visible, prefijo que activa la clasificación automática, minutos por defecto)
KINDS = {
    "exam": ("Evaluación (control, prueba, examen)", "Evaluación", 90),
    "deadline": ("Entrega (tarea, informe, proyecto)", "Entrega", 0),
    "class": ("Clase", "Clase", 90),
    "other": ("Otro (solo ocupa tiempo)", "", 60),
}
KIND_ORDER = ["exam", "deadline", "class", "other"]


def _parse_date(text, today=None):
    """Acepta dd/mm/aaaa, dd-mm-aaaa, dd/mm (año actual o siguiente) y aaaa-mm-dd."""
    today = today or date.today()
    t = text.strip().replace(".", "/").replace("-", "/")
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", t)
    if m:
        y, mo, d = map(int, m.groups())
        return date(y, mo, d)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
    if not m:
        raise ValueError("Fecha no válida. Usa dd/mm/aaaa (por ejemplo 22/10/2026).")
    d, mo = int(m.group(1)), int(m.group(2))
    if m.group(3):
        y = int(m.group(3))
        y += 2000 if y < 100 else 0
        return date(y, mo, d)
    cand = date(today.year, mo, d)
    if cand < today - timedelta(days=60):   # "10/01" en octubre -> enero del año siguiente
        cand = date(today.year + 1, mo, d)
    return cand


def parse_date(text, today=None):
    try:
        return _parse_date(text, today)
    except ValueError as exc:
        if "Fecha no válida" in str(exc):
            raise
        raise ValueError("Esa fecha no existe en el calendario. Revisa el día y el mes.") from None


def parse_time(text):
    m = re.fullmatch(r"(\d{1,2})[:.hH](\d{2})", text.strip())
    if not m:
        raise ValueError("Hora no válida. Usa HH:MM (por ejemplo 10:00).")
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise ValueError("Hora no válida. Usa HH:MM (por ejemplo 10:00).")
    return time(h, mi)


def make_item(title, kind, date_text, time_text, minutes, today=None):
    """Valida y arma un evento manual (dict listo para guardar en config)."""
    title = " ".join(title.split())
    if not title:
        raise ValueError("Escribe un título (por ejemplo: Cálculo).")
    if kind not in KINDS:
        raise ValueError("Tipo de evento no válido.")
    start = datetime.combine(parse_date(date_text, today), parse_time(time_text))
    return {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "kind": kind,
        "start": start.strftime("%Y-%m-%dT%H:%M"),
        "minutes": max(0, int(minutes)),
    }


def _summary(item):
    prefix = KINDS.get(item.get("kind"), KINDS["other"])[1]
    return f"{prefix} · {item['title']}" if prefix else item["title"]


def to_events(items):
    """Convierte los eventos guardados en Event (hora local) para el planificador."""
    events = []
    for it in items or []:
        try:
            start = datetime.strptime(it["start"], "%Y-%m-%dT%H:%M")
            end = start + timedelta(minutes=int(it.get("minutes", 0)))
            events.append(Event(_summary(it), start, end, False))
        except (KeyError, ValueError, TypeError):
            continue  # un registro dañado no debe romper el resto
    return events


def describe(item):
    try:
        start = datetime.strptime(item["start"], "%Y-%m-%dT%H:%M")
    except (KeyError, ValueError):
        return str(item.get("title", "?"))
    label = KINDS.get(item.get("kind"), KINDS["other"])[1] or "Evento"
    day = DAYS_ES[start.weekday()][:3].capitalize()
    return f"{day} {start:%d/%m %H:%M} · {label} · {item['title']}"


def purge_old(items, now=None, keep_days=7):
    """Quita los eventos que terminaron hace más de `keep_days` días."""
    now = now or datetime.now()
    kept = []
    for it in items or []:
        try:
            end = datetime.strptime(it["start"], "%Y-%m-%dT%H:%M") + timedelta(minutes=int(it.get("minutes", 0)))
        except (KeyError, ValueError, TypeError):
            continue
        if end >= now - timedelta(days=keep_days):
            kept.append(it)
    return sorted(kept, key=lambda i: i["start"])
