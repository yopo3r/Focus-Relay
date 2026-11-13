"""Cálculos del panel: calendario, racha, resumen semanal, estadísticas por etiqueta,
frase del día y exportación CSV. Son funciones puras (sin interfaz) para poder probarlas."""
import csv
import io
from datetime import date, datetime, timedelta


def category(mode):
    """El calendario agrupa trabajo (W) y descanso (D) del Pomodoro bajo 'P'."""
    return mode if mode in ("T", "C") else "P"


def session_date(session, today=None):
    """Fecha local de la sesión. Sin epoch (ESP sin hora sincronizada) se cuenta como hoy."""
    ep = session.get("epoch")
    if ep:
        return datetime.fromtimestamp(ep).date()
    return today or date.today()


def calendar_counts(log, today=None):
    """{date: {'T': n, 'C': n, 'P': n}}"""
    cal = {}
    for s in log:
        day = session_date(s, today)
        cat = category(s.get("modo"))
        cal.setdefault(day, {})
        cal[day][cat] = cal[day].get(cat, 0) + 1
    return cal


def streak(counts, today=None):
    """Días seguidos con al menos una sesión. Si hoy aún no hay, cuenta desde ayer."""
    today = today or date.today()
    cursor = today if today in counts else today - timedelta(days=1)
    n = 0
    while cursor in counts:
        n += 1
        cursor -= timedelta(days=1)
    return n


def week_start(now=None):
    """Medianoche del domingo de esta semana (el calendario empieza en domingo)."""
    now = now or datetime.now()
    sunday = now.date() - timedelta(days=(now.weekday() + 1) % 7)
    return datetime(sunday.year, sunday.month, sunday.day)


def week_summary(log, now=None):
    start = week_start(now)
    n, secs = 0, 0
    for s in log:
        ep = s.get("epoch")
        if s.get("modo") == "D":                  # los descansos no son enfoque
            continue
        if ep and datetime.fromtimestamp(ep) >= start:
            n += 1
            secs += int(s.get("duracion_seg", 0))
    return n, round(secs / 60)


def tag_stats(log):
    """[(etiqueta, {'seconds','sessions','done','undone'})] ordenado por tiempo total."""
    acc = {}
    for s in log:
        key = s.get("actividad") or ""
        a = acc.setdefault(key, {"seconds": 0, "sessions": 0, "done": 0, "undone": 0})
        a["seconds"] += int(s.get("duracion_seg", 0))
        a["sessions"] += 1
        if s.get("completada") is True:
            a["done"] += 1
        elif s.get("completada") is False:
            a["undone"] += 1
    return sorted(acc.items(), key=lambda kv: -kv[1]["seconds"])


def fmt_long(seconds):
    h, m = seconds // 3600, (seconds % 3600) // 60
    return f"{h}h {m}m" if h else f"{m}m"


def fmt_clock(seconds):
    v = max(0, min(5999, int(seconds or 0)))
    return f"{v // 60:02d}:{v % 60:02d}"


def phrase_of_day(defaults, custom, today=None):
    """Misma lógica de la web: una frase por día, rotando por día del año."""
    pool = list(defaults) + list(custom)
    if not pool:
        return ""
    today = today or date.today()
    day_of_year = (today - date(today.year, 1, 1)).days + 1
    return pool[day_of_year % len(pool)]


def month_grid(year, month):
    """Semanas del mes con domingo primero: lista de filas de 7 (None = vacío, int = día)."""
    first = date(year, month, 1)
    lead = (first.weekday() + 1) % 7
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    days = (nxt - first).days
    cells = [None] * lead + list(range(1, days + 1))
    cells += [None] * (-len(cells) % 7)
    return [cells[i:i + 7] for i in range(0, len(cells), 7)]


def _safe_cell(text):
    """Excel y LibreOffice ejecutan como fórmula una celda que empieza por = + - @ (inyección de CSV): se neutraliza."""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_csv(log, header, mode_name, no_date, locale_fmt=None):
    """Texto CSV: fecha,duracion_seg,tipo,actividad (igual que la web)."""
    out = io.StringIO()
    w = csv.writer(out, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    out.write(header + "\n")
    for s in log:
        ep = s.get("epoch")
        when = datetime.fromtimestamp(ep).strftime(locale_fmt or "%Y-%m-%d %H:%M:%S") if ep else no_date
        w.writerow([when, s.get("duracion_seg", 0), mode_name(s.get("modo")), _safe_cell(s.get("actividad") or "")])
    return out.getvalue()


def focus_minutes(log, since, until=None):
    """Minutos de enfoque (sin descansos) de las sesiones con epoch entre `since` y `until` (datetime)."""
    total = 0
    for s in log:
        ep = s.get("epoch")
        if not ep or s.get("modo") == "D":
            continue
        when = datetime.fromtimestamp(ep)
        if when >= since and (until is None or when < until):
            total += int(s.get("duracion_seg", 0))
    return round(total / 60)


def goal_progress(log, cfg, now=None):
    """[(clave, hecho_min, meta_min)] para las metas activas (diaria y semanal)."""
    now = now or datetime.now()
    out = []
    day, week = int(cfg.get("goal_daily_min") or 0), int(cfg.get("goal_weekly_min") or 0)
    if day > 0:
        out.append(("day", focus_minutes(log, now.replace(hour=0, minute=0, second=0, microsecond=0)), day))
    if week > 0:
        out.append(("week", focus_minutes(log, week_start(now)), week))
    return out
