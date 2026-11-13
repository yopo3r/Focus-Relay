"""Lectura de calendarios .ics y recomendación de sesiones de trabajo.

Todo corre localmente y sin dependencias externas: el .ics se interpreta
con un parser propio (con soporte de eventos repetidos semanales/diarios/
mensuales/anuales, zonas horarias y excepciones) y las sugerencias salen
de reglas simples, explicables y sin enviar datos a ningún servicio.

Cómo se decide qué estudiar:
  - Evaluaciones (prueba, control, examen, certamen...) próximas -> "Estudiar X".
    Cuanto más cerca está la fecha, más sesiones por día y mayor prioridad.
  - Entregas (tarea, informe, proyecto, entrega...) -> "Avanzar X".
  - Clases (cátedra, auxiliar, laboratorio...) -> "Repasar X" poco después
    de la clase, cuando el repaso retiene más.
  - Las sesiones se ubican en los huecos libres entre eventos, dentro del
    horario de estudio, con margen antes/después de cada evento. La
    duración se ajusta al hueco (por ejemplo 35 min si el hueco no da más).
"""
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------
@dataclass
class Event:
    summary: str
    start: datetime          # hora local, sin tzinfo
    end: datetime
    all_day: bool = False


@dataclass
class Suggestion:
    start: datetime
    end: datetime
    minutes: int
    title: str
    reason: str
    kind: str                # "exam" | "deadline" | "review"
    subject: str


@dataclass
class PlannerConfig:
    day_start: int = 8               # hora en que empieza el horario de estudio
    day_end: int = 22                # hora en que termina
    horizon_days: int = 7
    max_sessions_per_day: int = 4
    min_minutes: int = 20
    focus_minutes: int = 50          # duración máxima para estudiar/avanzar
    review_minutes: int = 25         # duración de un repaso
    buffer_before: int = 10          # margen antes de un evento
    buffer_after: int = 5            # margen después de un evento
    break_minutes: int = 10          # pausa entre sesiones consecutivas
    hour_scores: dict = field(default_factory=dict)   # {hora: 0..1} de tus mejores horas (vacío = sin adaptar)
    adapted: bool = False            # focus_minutes viene de lo que sueles completar


# ---------------------------------------------------------------------------
# Parser iCalendar
# ---------------------------------------------------------------------------
def _unfold(text):
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _split_line(line):
    in_quotes = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ":" and not in_quotes:
            head, value = line[:i], line[i + 1:]
            break
    else:
        return None
    parts = head.split(";")
    params = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.upper()] = v.strip('"')
    return parts[0].upper(), params, value


def _unescape(v):
    return (
        v.replace("\\n", " ").replace("\\N", " ")
        .replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
        .strip()
    )


def _parse_dt(value, params):
    """Devuelve (hora_de_pared_naive, tz|None, es_todo_el_día)."""
    v = value.strip()
    if params.get("VALUE", "").upper() == "DATE" or (len(v) == 8 and v.isdigit()):
        return datetime.strptime(v[:8], "%Y%m%d"), None, True
    utc = v.endswith("Z")
    v = v.rstrip("Z")
    fmt = "%Y%m%dT%H%M%S" if len(v) >= 15 else "%Y%m%dT%H%M"
    dt = datetime.strptime(v, fmt)
    tz = None
    if utc:
        tz = timezone.utc
    elif "TZID" in params and ZoneInfo is not None:
        try:
            tz = ZoneInfo(params["TZID"])
        except Exception:
            tz = None  # zona desconocida: se asume hora local del equipo
    return dt, tz, False


def _to_local(wall, tz):
    if tz is None:
        return wall
    return wall.replace(tzinfo=tz).astimezone().replace(tzinfo=None)


def _parse_duration(v):
    m = re.fullmatch(
        r"([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", v.strip()
    )
    if not m:
        return None
    sign = -1 if m.group(1) == "-" else 1
    w, d, h, mi, s = (int(x) if x else 0 for x in m.groups()[1:])
    return sign * timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)


_WD = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def _parse_rrule(value):
    rule = {}
    for part in value.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            rule[k.upper()] = v
    return rule


def _expand_rule(start, rule, limit, until):
    """Genera horas de pared de una serie repetida, desde `start` hasta `limit`."""
    freq = rule.get("FREQ", "").upper()
    try:
        interval = max(1, int(rule.get("INTERVAL", "1")))
    except ValueError:
        interval = 1
    count = int(rule["COUNT"]) if rule.get("COUNT", "").isdigit() else None
    n = 0

    def allowed(dt):
        return dt <= limit and (until is None or dt <= until)

    if freq == "DAILY":
        cur = start
        for _ in range(20000):
            if not allowed(cur):
                return
            yield cur
            n += 1
            if count and n >= count:
                return
            cur += timedelta(days=interval)

    elif freq == "WEEKLY":
        codes = [re.sub(r"[^A-Z]", "", d) for d in rule.get("BYDAY", "").split(",") if d]
        wds = sorted({_WD[c] for c in codes if c in _WD}) or [start.weekday()]
        week0 = start - timedelta(days=start.weekday())
        for k in range(5000):
            base = week0 + timedelta(weeks=k * interval)
            if base > limit:
                return
            for wd in wds:
                dt = base + timedelta(days=wd)
                if dt < start:
                    continue
                if not allowed(dt):
                    return
                yield dt
                n += 1
                if count and n >= count:
                    return

    elif freq in ("MONTHLY", "YEARLY"):
        cur_y, cur_m = start.year, start.month
        for _ in range(2000):
            try:
                dt = start.replace(year=cur_y, month=cur_m)
            except ValueError:
                dt = None  # p. ej. día 31 en un mes de 30 días
            if dt is not None:
                if not allowed(dt):
                    if dt > limit or (until is not None and dt > until):
                        return
                else:
                    yield dt
                    n += 1
                    if count and n >= count:
                        return
            if freq == "MONTHLY":
                total = cur_y * 12 + (cur_m - 1) + interval
                cur_y, cur_m = divmod(total, 12)
                cur_m += 1
            else:
                cur_y += interval
            if cur_y > limit.year + 1:
                return
    else:
        if allowed(start):
            yield start


def _vevents(text):
    events, cur = [], None
    for line in _unfold(text):
        up = line.strip().upper()
        if up == "BEGIN:VEVENT":
            cur = {}
        elif up == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
        elif cur is not None:
            parsed = _split_line(line)
            if parsed:
                name, params, value = parsed
                cur.setdefault(name, []).append((params, value))
    return events


def load_events(text, window_start, window_end):
    """Devuelve los eventos (ya expandidos) que caen en la ventana, en hora local."""
    limit = window_end + timedelta(days=2)
    raw = _vevents(text)

    def first(ev, name):
        return ev[name][0] if name in ev else None

    # Ocurrencias que fueron movidas/canceladas individualmente.
    overridden = set()
    for ev in raw:
        rid = first(ev, "RECURRENCE-ID")
        uid = first(ev, "UID")
        if rid and uid:
            try:
                wall, tz, _ = _parse_dt(rid[1], rid[0])
                overridden.add((uid[1], _to_local(wall, tz)))
            except ValueError:
                pass

    out = []
    for ev in raw:
        status = first(ev, "STATUS")
        if status and status[1].strip().upper() == "CANCELLED":
            continue
        ds = first(ev, "DTSTART")
        if not ds:
            continue
        try:
            wall, tz, all_day = _parse_dt(ds[1], ds[0])
        except ValueError:
            continue
        local_start = _to_local(wall, tz)

        delta = None
        de = first(ev, "DTEND")
        if de:
            try:
                ew, etz, _ = _parse_dt(de[1], de[0])
                delta = _to_local(ew, etz) - local_start
            except ValueError:
                delta = None
        if delta is None:
            dur = first(ev, "DURATION")
            delta = _parse_duration(dur[1]) if dur else None
        if delta is None or delta < timedelta(0):
            delta = timedelta(days=1) if all_day else timedelta(0)

        summary = _unescape(first(ev, "SUMMARY")[1]) if first(ev, "SUMMARY") else "(sin título)"
        uid = first(ev, "UID")
        uid = uid[1] if uid else None

        if "RRULE" in ev and "RECURRENCE-ID" not in ev:
            rule = _parse_rrule(ev["RRULE"][0][1])
            until = None
            if rule.get("UNTIL"):
                try:
                    uw, utz, ud = _parse_dt(rule["UNTIL"], {})
                    until = uw + timedelta(days=1) - timedelta(seconds=1) if ud else (
                        uw.replace(tzinfo=utz).astimezone(tz).replace(tzinfo=None)
                        if (utz is not None and tz is not None) else uw
                    )
                except ValueError:
                    until = None
            excluded = set()
            for params, value in ev.get("EXDATE", []):
                for piece in value.split(","):
                    try:
                        xw, xtz, _ = _parse_dt(piece, params)
                        excluded.add(_to_local(xw, xtz))
                    except ValueError:
                        pass
            for occ in _expand_rule(wall, rule, limit, until):
                s = occ if all_day else _to_local(occ, tz)
                if s in excluded or (uid and (uid, s) in overridden):
                    continue
                out.append(Event(summary, s, s + delta, all_day))
        else:
            out.append(Event(summary, local_start, local_start + delta, all_day))

    seen, result = set(), []
    for e in sorted(out, key=lambda e: (e.start, e.end, e.summary)):
        key = (e.summary, e.start, e.end)
        if key in seen:
            continue
        seen.add(key)
        if e.end > window_start and e.start < window_end or (
            e.start == e.end and window_start <= e.start < window_end
        ):
            result.append(e)
    return result


# ---------------------------------------------------------------------------
# Clasificación de eventos
# ---------------------------------------------------------------------------
def _norm(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


STRONG_DEADLINE = ["entrega", "deadline", "due", "fecha limite"]
EXAM_WORDS = ["prueba", "control", "examen", "certamen", "evaluacion", "quiz", "solemne",
              "parcial", "interrogacion", "exam", "midterm", "recuperativo", "recuperativa"]
DEADLINE_WORDS = ["tarea", "informe", "proyecto", "hito", "avance", "presentacion",
                  "paper", "ensayo", "reporte", "taller entregable"]
CLASS_WORDS = ["clase", "catedra", "auxiliar", "laboratorio", "lab", "taller", "ayudantia",
               "lecture", "seminario", "tutorial", "practico", "workshop", "curso"]

_EXAM_RE = re.compile(r"\b(" + "|".join(EXAM_WORDS) + r"|c[1-4]|i[1-3])\b")
_STRONG_RE = re.compile(r"\b(" + "|".join(STRONG_DEADLINE) + r")\b")
_DEADLINE_RE = re.compile(r"\b(" + "|".join(DEADLINE_WORDS) + r")\b")
_CLASS_RE = re.compile(r"\b(" + "|".join(CLASS_WORDS) + r")\b")
_CODE_RE = re.compile(r"\b[A-Za-z]{2,3}\s?-?\d{3,4}(?:-\d+)?\b")


def classify(summary):
    """Devuelve 'exam', 'deadline', 'class' u 'other' según el título del evento."""
    n = _norm(summary)
    if _STRONG_RE.search(n):
        return "deadline"
    if _EXAM_RE.search(n):
        return "exam"
    if _DEADLINE_RE.search(n):
        return "deadline"
    if _CLASS_RE.search(n) or _CODE_RE.search(summary):
        return "class"
    return "other"


_CONNECTORS = {"de", "del", "la", "el", "los", "las", "para", "en", "y", "con"}


def extract_subject(summary, kind):
    """Saca el nombre del ramo/tarea: 'Control 2 - Cálculo (MA2001)' -> 'Cálculo'."""
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", summary)
    s = _CODE_RE.sub(" ", s)
    parts = [p.strip() for p in re.split(r"\s[-–—]\s|[:|·/,]", s) if p.strip()]
    if kind == "deadline":
        drop = set(STRONG_DEADLINE)
    elif kind == "exam":
        drop = set(EXAM_WORDS) | {"c1", "c2", "c3", "c4", "i1", "i2", "i3"}
    else:
        drop = set(CLASS_WORDS)
    cleaned = []
    for part in parts:
        toks = [t for t in part.split()
                if _norm(t) not in drop
                and (kind == "deadline" or not re.fullmatch(r"(n[°º]?)?\d+[ªº°]?", _norm(t)))]
        while toks and _norm(toks[0]) in _CONNECTORS:
            toks.pop(0)
        while toks and _norm(toks[-1]) in _CONNECTORS:
            toks.pop()
        if toks:
            cleaned.append(" ".join(toks))
    if not cleaned:
        return re.sub(r"\s+", " ", s).strip() or summary.strip()
    if kind == "deadline":
        return " – ".join(cleaned)
    return max(cleaned, key=len)


# ---------------------------------------------------------------------------
# Recomendación
# ---------------------------------------------------------------------------
@dataclass
class _Target:
    kind: str
    subject: str
    need: int                 # minutos de estudio que faltan por ubicar
    due: Optional[datetime]   # fecha límite (evaluación/entrega)
    event_summary: str
    not_before: Optional[datetime] = None   # repaso: no antes del fin de la clase
    not_after: Optional[datetime] = None    # repaso: no más de 6 h después
    class_end: Optional[datetime] = None


def _ceil5(dt):
    dt = dt.replace(second=0, microsecond=0)
    return dt + timedelta(minutes=(-dt.minute) % 5)


def _floor5(m):
    return int(m // 5) * 5


def _ceil5_int(m):
    return int(math.ceil(m / 5.0) * 5)


def _build_targets(events, now, cfg):
    targets = []
    horizon_end = now + timedelta(days=cfg.horizon_days + 1)
    reviews = {}
    for e in events:
        kind = classify(e.summary)
        if kind == "exam":
            due = datetime.combine(e.start.date(), time(8, 0)) if e.all_day else e.start
            if now < due <= now + timedelta(days=8):
                targets.append(_Target("exam", extract_subject(e.summary, "exam"), 400, due, e.summary))
        elif kind == "deadline":
            due = datetime.combine(e.start.date(), time(23, 59)) if e.all_day else e.start
            if now < due <= now + timedelta(days=7):
                targets.append(_Target("deadline", extract_subject(e.summary, "deadline"), 240, due, e.summary))
        elif kind == "class" and not e.all_day:
            if now - timedelta(hours=6) <= e.end <= horizon_end:
                subj = extract_subject(e.summary, "class")
                key = (_norm(subj), e.end.date())
                prev = reviews.get(key)
                if prev is None or e.end > prev[0]:
                    reviews[key] = (e.end, subj, e.summary, (prev[3] if prev else 0) + 1)
                else:
                    reviews[key] = (prev[0], prev[1], prev[2], prev[3] + 1)
    for (_, _), (end, subj, summ, n) in reviews.items():
        targets.append(_Target("review", subj, cfg.review_minutes * min(n, 2), None, summ,
                               not_before=end, not_after=end + timedelta(hours=6), class_end=end))
    return targets


def _gaps(lo, hi, busy):
    busy = sorted((max(s, lo), min(e, hi)) for s, e in busy if e > lo and s < hi)
    gaps, cur = [], lo
    for s, e in busy:
        if s > cur:
            gaps.append((cur, s))
        cur = max(cur, e)
    if cur < hi:
        gaps.append((cur, hi))
    return gaps


def _day_quota(kind, days_left):
    """Minutos de estudio por día para una materia, según cuán cerca está la fecha.

    Reparte el esfuerzo en vez de concentrarlo: poco al principio y más a
    medida que se acerca la evaluación o la entrega.
    """
    if kind == "exam":
        return 25 if days_left >= 6 else 45 if days_left >= 3 else 60 if days_left >= 1 else 50
    if kind == "deadline":
        return 25 if days_left >= 4 else 45 if days_left >= 2 else 60
    return 0


def _pick(targets, cur, gap_end, day, per_target, last_key, cfg):
    best = None
    for t in targets:
        if t.need < cfg.min_minutes - 4:
            continue
        key = id(t)
        if t.kind == "review":
            if cur < t.not_before or cur > t.not_after or t.not_before.date() != day:
                continue
            days_left = 99
        else:
            if t.due <= cur:
                continue
            days_left = (t.due.date() - day).days
        used = per_target.get(key, 0)
        remaining = t.need if t.kind == "review" else _day_quota(t.kind, days_left) - used
        if remaining < cfg.min_minutes:
            continue

        avail = (gap_end - cur).total_seconds() / 60.0
        if t.due is not None:
            avail = min(avail, (t.due - cur).total_seconds() / 60.0 - 10)
        pref = cfg.review_minutes if t.kind == "review" else cfg.focus_minutes
        dur = _floor5(min(pref, avail, _ceil5_int(t.need), remaining))
        if dur < cfg.min_minutes:
            continue

        if t.kind == "exam":
            score = 100 + 40.0 / (days_left + 1)
        elif t.kind == "deadline":
            score = 80 + 30.0 / (days_left + 1)
        else:
            since = (cur - t.class_end).total_seconds() / 60.0
            score = 50 + (20 if since <= 90 else 10 if since <= 180 else 0)
        if last_key == key:
            score -= 15  # intercalar materias
        if best is None or score > best[0]:
            best = (score, t, dur)
    return None if best is None else (best[1], best[2])


def _rel_day(d, today):
    diff = (d - today).days
    if diff == 0:
        return "hoy"
    if diff == 1:
        return "mañana"
    return f"el {DAYS_ES[d.weekday()]} {d.day:02d}/{d.month:02d}"


def _reason(t, today):
    if t.kind == "exam":
        when = _rel_day(t.due.date(), today)
        hhmm = f" a las {t.due:%H:%M}"
        days_left = (t.due.date() - today).days
        extra = f" (faltan {days_left} días)" if days_left > 1 else ""
        return f"«{t.event_summary}» {when}{hhmm}{extra}. Estudiar con anticipación y en varias sesiones rinde más."
    if t.kind == "deadline":
        when = _rel_day(t.due.date(), today)
        hhmm = "" if t.due.hour == 23 and t.due.minute == 59 else f" a las {t.due:%H:%M}"
        return f"«{t.event_summary}» vence {when}{hhmm}. Avanzar un poco cada día evita el apuro final."
    return (f"Tu clase «{t.event_summary}» termina a las {t.class_end:%H:%M}. "
            "Repasar poco después de la clase ayuda a fijar lo visto.")


def _best_start(g0, g1, cfg):
    """Con horas favoritas conocidas, empieza el hueco en la mejor hora si cabe una sesión; si no, al inicio."""
    start = _ceil5(g0)
    if not cfg.hour_scores:
        return start
    need = timedelta(minutes=cfg.min_minutes + cfg.break_minutes)
    best, best_score = start, cfg.hour_scores.get(start.hour, 0.0)
    cand = start.replace(minute=0) + timedelta(hours=1)
    while g1 - cand >= need:
        sc = cfg.hour_scores.get(cand.hour, 0.0)
        if sc > best_score + 0.25:
            best, best_score = cand, sc
        cand += timedelta(hours=1)
    return best


def recommend(events, now, cfg=None):
    """Arma la lista de sesiones sugeridas (ordenadas por fecha)."""
    cfg = cfg or PlannerConfig()
    now = _ceil5(now)
    targets = _build_targets(events, now, cfg)
    timed = [e for e in events if not e.all_day]
    suggestions = []

    for offset in range(cfg.horizon_days + 1):
        day = (now + timedelta(days=offset)).date()
        lo = max(datetime.combine(day, time(cfg.day_start)), now)
        hi = (datetime.combine(day, time(0)) + timedelta(hours=min(cfg.day_end, 24)))
        if (hi - lo) < timedelta(minutes=cfg.min_minutes):
            continue
        busy = [(e.start - timedelta(minutes=cfg.buffer_before),
                 e.end + timedelta(minutes=cfg.buffer_after))
                for e in timed if e.end > lo and e.start < hi]
        count, last_key, per_target = 0, None, {}
        for g0, g1 in _gaps(lo, hi, busy):
            cur = _ceil5(_best_start(g0, g1, cfg))
            while count < cfg.max_sessions_per_day and (g1 - cur) >= timedelta(minutes=cfg.min_minutes):
                pick = _pick(targets, cur, g1, day, per_target, last_key, cfg)
                if pick is None:
                    break
                t, dur = pick
                end = cur + timedelta(minutes=dur)
                verb = {"exam": "Estudiar", "deadline": "Avanzar", "review": "Repasar"}[t.kind]
                note = ""
                if cfg.hour_scores and cfg.hour_scores.get(cur.hour, 0) >= 0.6:
                    note += " Es una de tus mejores horas según tu historial."
                if cfg.adapted and t.kind != "review" and dur == cfg.focus_minutes:
                    note += f" Duración ajustada a lo que sueles completar ({dur} min)."
                suggestions.append(Suggestion(cur, end, dur, f"{verb} {t.subject}",
                                              _reason(t, now.date()) + note, t.kind, t.subject))
                t.need -= dur
                per_target[id(t)] = per_target.get(id(t), 0) + dur
                last_key = id(t)
                count += 1
                cur = _ceil5(end + timedelta(minutes=cfg.break_minutes))
    return suggestions


def describe(s):
    """'Estudiar Cálculo · 35 min' para mostrar o copiar."""
    return f"{s.title} · {s.minutes} min"
