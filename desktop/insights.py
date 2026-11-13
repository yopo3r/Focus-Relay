"""Estadísticas por período (día / semana / mes / año / todo) y logros. Funciones puras.

"Tiempo enfocado" = Temporizador + Cronómetro + trabajo del Pomodoro (no cuenta los descansos).
Una sesión "completada" es la que llegó a 00:00 (completada = True); las demás son cortadas antes.
"""
from datetime import date, datetime, timedelta

import stats


def _load_cfg():
    try:
        from config import load_config
        return load_config()
    except Exception:
        return {}

KINDS = ("day", "week", "month", "year", "all")


def is_focus(s):
    return s.get("modo") != "D"


def completed(s):
    return s.get("completada") is True


def bounds(kind, anchor, log=None):
    """(inicio, fin) inclusivos del período que contiene `anchor`. 'all' usa la primera sesión."""
    if kind == "day":
        return anchor, anchor
    if kind == "week":
        start = anchor - timedelta(days=(anchor.weekday() + 1) % 7)       # semana que empieza en domingo
        return start, start + timedelta(days=6)
    if kind == "month":
        start = anchor.replace(day=1)
        nxt = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
        return start, nxt - timedelta(days=1)
    if kind == "year":
        return date(anchor.year, 1, 1), date(anchor.year, 12, 31)
    days = [stats.session_date(s) for s in (log or [])]
    return (min(days) if days else anchor), max(anchor, max(days) if days else anchor)


def shift(kind, anchor, n):
    """Mueve `anchor` n períodos (n=-1 anterior, +1 siguiente)."""
    if kind == "day":
        return anchor + timedelta(days=n)
    if kind == "week":
        return anchor + timedelta(weeks=n)
    if kind == "month":
        m = anchor.month - 1 + n
        return date(anchor.year + m // 12, m % 12 + 1, 1)
    if kind == "year":
        return date(anchor.year + n, 1, 1)
    return anchor


def _in(s, start, end):
    return start <= stats.session_date(s) <= end


def _metrics(sessions):
    focus = [s for s in sessions if is_focus(s)]
    secs = sum(int(s.get("duracion_seg", 0)) for s in focus)
    judged = [s for s in focus if s.get("modo") != "C"]     # el cronómetro no tiene meta: no cuenta como "cortado"
    done = sum(1 for s in judged if completed(s))
    cut = sum(1 for s in judged if s.get("completada") is False)
    longest = max((int(s.get("duracion_seg", 0)) for s in focus), default=0)
    days = {stats.session_date(s) for s in focus}
    return {
        "focus_s": secs, "sessions": len(focus), "completed": done, "cut": cut,
        "rate": round(100 * done / (done + cut)) if (done + cut) else None,
        "avg_s": round(secs / len(focus)) if focus else 0, "longest_s": longest, "active_days": len(days),
    }


def period_stats(log, kind, anchor, tasks_by_date=None, today=None):
    today = today or date.today()
    start, end = bounds(kind, anchor, log)
    inside = [s for s in log if _in(s, start, end)]
    m = _metrics(inside)
    focus = [s for s in inside if is_focus(s)]

    # tiempo por día (mejor día)
    per_day = {}
    for s in focus:
        d = stats.session_date(s)
        per_day[d] = per_day.get(d, 0) + int(s.get("duracion_seg", 0))
    best = max(per_day.items(), key=lambda kv: kv[1]) if per_day else None

    # barras del gráfico
    buckets = []
    if kind == "day":
        hours = [0] * 24
        for s in focus:
            if s.get("epoch"):
                hours[datetime.fromtimestamp(s["epoch"]).hour] += int(s.get("duracion_seg", 0))
            else:
                hours[datetime.now().hour] += int(s.get("duracion_seg", 0))
        buckets = [(f"{h:02d}", hours[h], None) for h in range(24)]
    elif kind in ("week", "month"):
        d = start
        while d <= end:
            buckets.append((d.day if kind == "month" else d.weekday(), per_day.get(d, 0), d))
            d += timedelta(days=1)
    elif kind == "year":
        months = [0] * 12
        for d, v in per_day.items():
            months[d.month - 1] += v
        buckets = [(i, months[i], date(start.year, i + 1, 1)) for i in range(12)]
    else:
        by_month = {}
        for d, v in per_day.items():
            by_month[(d.year, d.month)] = by_month.get((d.year, d.month), 0) + v
        keys = sorted(by_month)
        if len(keys) > 24:                                   # muchos años: agrupa por año
            by_year = {}
            for (y, _m), v in by_month.items():
                by_year[y] = by_year.get(y, 0) + v
            buckets = [(str(y), v, date(y, 1, 1)) for y, v in sorted(by_year.items())]
        else:
            buckets = [(f"{m:02d}", by_month[(y, m)], date(y, m, 1)) for (y, m) in keys]

    by_mode = {"T": 0, "C": 0, "P": 0}
    for s in focus:
        by_mode[stats.category(s.get("modo"))] += int(s.get("duracion_seg", 0))
    tags = [(k or "", v) for k, v in stats.tag_stats(focus)]

    prev = None
    if kind != "all":
        ps, pe = bounds(kind, shift(kind, anchor, -1))
        pm = _metrics([s for s in log if _in(s, ps, pe)])
        prev = {"focus_s": pm["focus_s"], "sessions": pm["sessions"]}
    tasks_done = sum(v for d, v in (tasks_by_date or {}).items() if start <= d <= end)
    return {"kind": kind, "start": start, "end": end, **m, "best_day": best, "buckets": buckets,
            "by_mode": by_mode, "tags": tags, "prev": prev, "tasks_done": tasks_done,
            "is_current": start <= today <= end}


def delta_pct(now, before):
    """Variación porcentual (None si no hay base para comparar)."""
    if not before:
        return None
    return round(100 * (now - before) / before)


# ---------------------------------------------------------------- racha y logros
def best_streak(counts, days=None):
    days = days or stats.ALL_DAYS
    best = run = 0
    prev = None
    for d in sorted(counts):
        if prev is not None:
            gap = (d - prev).days
            ok = all((prev + timedelta(days=k)).weekday() not in days for k in range(1, gap))
            run = run + 1 if ok else 1
        else:
            run = 1
        best, prev = max(best, run), d
    return best


def totals(log, tasks_by_date=None, today=None, streak_days=None):
    counts = stats.calendar_counts([s for s in log if is_focus(s)], today)
    if streak_days is None:
        streak_days = stats.streak_days(_load_cfg())
    focus = [s for s in log if is_focus(s)]
    return {
        "streak": stats.streak(counts, today, streak_days), "best_streak": best_streak(counts, streak_days),
        "hours": sum(int(s.get("duracion_seg", 0)) for s in focus) / 3600.0,
        "sessions": sum(1 for s in focus if completed(s)),
        "pomodoros": sum(1 for s in log if s.get("modo") == "W" and completed(s)),
        "tasks": sum((tasks_by_date or {}).values()),
        "longest_min": max((int(s.get("duracion_seg", 0)) for s in focus), default=0) // 60,
        "active_days": len(counts),
    }


# (id de familia, métrica, umbrales)
FAMILIES = [
    ("streak", "best_streak", (3, 7, 14, 30, 60, 100, 365)),
    ("hours", "hours", (1, 10, 25, 50, 100, 250, 500, 1000)),
    ("sessions", "sessions", (1, 10, 50, 100, 250, 500, 1000)),
    ("tasks", "tasks", (10, 50, 100, 250, 500)),
    ("marathon", "longest_min", (25, 45, 60, 90, 120, 180)),
]


def achievements(tot):
    """[{id, family, goal, value, unlocked}] en orden de familia y umbral."""
    out = []
    for fam, metric, goals in FAMILIES:
        for g in goals:
            v = tot.get(metric, 0)
            out.append({"id": f"{fam}_{g}", "family": fam, "goal": g, "value": v, "unlocked": v >= g})
    return out


def next_goal(tot, family):
    for fam, metric, goals in FAMILIES:
        if fam == family:
            v = tot.get(metric, 0)
            for g in goals:
                if v < g:
                    return g, v
    return None, tot.get(family, 0)


def last_days(counts, n=7, today=None):
    """[(fecha, ¿hubo sesión?)] de los últimos n días terminando hoy."""
    today = today or date.today()
    return [(today - timedelta(days=i), (today - timedelta(days=i)) in counts) for i in range(n - 1, -1, -1)]
