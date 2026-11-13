"""Adaptación a tu uso: reglas estadísticas simples y explicables sobre tu propio historial. Funciones puras.

Nada sale del equipo y nada cambia hasta tener datos suficientes (MIN_SESSIONS sesiones de enfoque).
`analyze()` devuelve un perfil; `tips()` lo convierte en consejos [(clave_i18n, {parámetros})] que
siempre incluyen el porqué (las cifras en que se basan).
"""
from datetime import datetime, timedelta
from statistics import median

MIN_SESSIONS = 10          # por debajo de esto no se adapta nada
RECENT_DAYS = 60           # solo cuenta el uso reciente
MIN_DUR, MAX_DUR = 15, 90


def _r5(x):
    return int(round(x / 5.0)) * 5


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _focus(log, since):
    """Sesiones de enfoque (sin descansos) con hora conocida: [(inicio, minutos, completada, actividad)]."""
    out = []
    for s in log:
        ep, dur = s.get("epoch"), s.get("duracion_seg")
        if not ep or not isinstance(dur, (int, float)) or s.get("modo") == "D":
            continue
        end = datetime.fromtimestamp(ep)
        if end < since:
            continue
        out.append((end - timedelta(seconds=dur), dur / 60.0, s.get("completada") is True,
                    (s.get("actividad") or "").strip()))
    out.sort(key=lambda x: x[0])
    return out


def analyze(log, cfg=None, now=None):
    cfg = cfg or {}
    now = now or datetime.now()
    sess = _focus(log, now - timedelta(days=RECENT_DAYS))
    p = {"n": len(sess), "min": MIN_SESSIONS, "ready": len(sess) >= MIN_SESSIONS,
         "rate": None, "duration": None, "stop_at": None, "hours": {}, "best_hours": [],
         "goal": None, "tags": [], "skip_breaks": None, "fatigue_after": None, "fatigue_now": False}
    if not sess:
        return p
    done = [s for s in sess if s[2]]
    p["rate"] = round(100 * len(done) / len(sess))

    # (1) duración: lo que sueles completar; si cortas mucho, el punto donde sueles cortar
    cut = [s[1] for s in sess if not s[2] and s[1] >= 5]
    if len(done) >= 3:
        d = _clamp(_r5(median(s[1] for s in done)), MIN_DUR, MAX_DUR)
        if p["rate"] < 60 and len(cut) >= 3:
            p["stop_at"] = round(median(cut))
            d = _clamp(min(d, (int(median(cut)) // 5) * 5), MIN_DUR, MAX_DUR)
        p["duration"] = d

    # (2) horas: minutos completados por hora de inicio (los cortados pesan menos)
    score = {}
    for start, mins, ok, _ in sess:
        score[start.hour] = score.get(start.hour, 0.0) + mins * (1.0 if ok else 0.3)
    top = max(score.values())
    p["hours"] = {h: round(v / top, 2) for h, v in score.items()}
    p["best_hours"] = [h for h, _ in sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]

    # (3) meta diaria: contra los días activos de las últimas 2 semanas
    days = {}
    for start, mins, _, _ in sess:
        if start >= now - timedelta(days=14):
            days[start.date()] = days.get(start.date(), 0.0) + mins
    goal = int(cfg.get("goal_daily_min") or 0)
    if len(days) >= 5:
        vals = sorted(days.values())
        med = median(vals)
        if goal > 0:
            rate = round(100 * sum(1 for v in vals if v >= goal) / len(vals))
            if rate < 30:
                p["goal"] = {"kind": "lower", "value": max(10, _r5(med)), "rate": rate, "current": goal}
            elif rate > 85:
                p["goal"] = {"kind": "raise", "value": _r5(goal * 1.2) or goal + 5, "rate": rate, "current": goal}
        else:
            p["goal"] = {"kind": "set", "value": max(10, _r5(med)), "rate": None, "current": 0}

    # (4) estimaciones por tarea / etiqueta
    tags = {}
    for _, mins, ok, tag in sess:
        if tag:
            tags.setdefault(tag, []).append((mins, ok))
    rows = []
    for tag, v in tags.items():
        if len(v) >= 3:
            rows.append({"tag": tag, "n": len(v), "typical": max(5, _r5(median(m for m, _ in v))),
                         "total": round(sum(m for m, _ in v))})
    p["tags"] = sorted(rows, key=lambda r: -r["total"])[:5]

    # (5) ritmo: ¿te saltas los descansos del Pomodoro?
    breaks = [s for s in log if s.get("modo") == "D" and s.get("epoch")
              and datetime.fromtimestamp(s["epoch"]) >= now - timedelta(days=RECENT_DAYS)]
    if len(breaks) >= 5:
        p["skip_breaks"] = round(100 * sum(1 for s in breaks if s.get("completada") is not True) / len(breaks))

    # (6) cansancio: completas menos a partir de cierta sesión del día
    by_day = {}
    for s in sess:
        by_day.setdefault(s[0].date(), []).append(s)
    early, late = [], []
    for lst in by_day.values():
        for i, s in enumerate(lst):
            (early if i < 3 else late).append(s[2])
    if len(late) >= 4 and len(early) >= 6:
        e, l = 100 * sum(early) / len(early), 100 * sum(late) / len(late)
        if e - l >= 25:
            p["fatigue_after"] = 3
            p["fatigue_drop"] = (round(e), round(l))
            p["fatigue_now"] = len(by_day.get(now.date(), [])) >= 3
    return p


def hour_scores(profile):
    """{hora: 0..1} para el planificador; vacío si aún no hay datos suficientes."""
    return dict(profile["hours"]) if profile.get("ready") else {}


def recommended_minutes(profile):
    return profile.get("duration") if profile.get("ready") else None


def estimate_for(profile, tag):
    """Duración típica de una sesión con esa etiqueta, o None."""
    if not profile.get("ready"):
        return None
    for r in profile["tags"]:
        if r["tag"] == tag:
            return r["typical"]
    return None


def tips(p):
    """Consejos personalizados: [(clave, parámetros)]. Cada uno explica sus cifras."""
    if not p["ready"]:
        return [("adTipPoco", {"n": p["n"], "min": p["min"]})]
    out = []
    if p["duration"]:
        out.append(("adTipDuracion" if p["rate"] >= 60 else "adTipDuracionCorta",
                    {"m": p["duration"], "rate": p["rate"], "stop": p["stop_at"] or 0}))
    if p["best_hours"]:
        hs = sorted(p["best_hours"])
        out.append(("adTipHoras", {"h": ", ".join(f"{h:02d}:00" for h in hs)}))
    g = p["goal"]
    if g:
        out.append(({"lower": "adTipMetaBaja", "raise": "adTipMetaSube", "set": "adTipMetaNueva"}[g["kind"]],
                    {"v": g["value"], "rate": g["rate"] or 0, "cur": g["current"]}))
    if p["tags"]:
        r = p["tags"][0]
        out.append(("adTipTarea", {"tag": r["tag"], "m": r["typical"], "n": r["n"]}))
    if p["skip_breaks"] is not None and p["skip_breaks"] >= 50:
        out.append(("adTipDescansos", {"pct": p["skip_breaks"]}))
    if p["fatigue_after"]:
        e, l = p["fatigue_drop"]
        out.append(("adTipCansancio", {"n": p["fatigue_after"], "e": e, "l": l}))
    return out


def fatigue_notice(p):
    """Aviso al iniciar una sesión cuando hoy ya pasaste tu punto de cansancio; None si no aplica."""
    if p.get("ready") and p.get("fatigue_now"):
        return ("adAvisoCansancio", {"n": p["fatigue_after"]})
    return None


def load_profile(cfg=None):
    """Perfil del historial actual (local o dispositivo). None si está desactivado o no se pudo leer."""
    from config import load_config
    import esp_client
    cfg = cfg or load_config()
    if not cfg.get("adaptive", True):
        return None
    try:
        log = esp_client.get_log(esp_client.url_of(cfg))
    except Exception:
        log = None
    return analyze(log, cfg) if log is not None else None
