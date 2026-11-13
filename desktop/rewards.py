"""Premios (piezas de colección) por fase de trabajo completada.

Misma regla que la extensión: el firmware cuenta `sesionesTrabajoCompletadas` y expone
`idArranque`; cada vez que el contador sube dentro del mismo arranque, se entrega una
pieza por cada fase completada. Cancelaciones y saltos no cuentan. La pieza depende de un
hash de "arranque|n", así que la app y la extensión eligen las mismas piezas.
"""
import time

POOLS = {
    "trenes": ["🚆", "🚄", "🚂", "🚇", "🚋"],
    "autos": ["🚗", "🏎️", "🚙", "🚕", "🛻"],
    "animales": ["🦊", "🐼", "🐯", "🦉", "🐬"],
    "espacio": ["🚀", "🪐", "🌙", "🛰️", "⭐"],
    "naturaleza": ["🌲", "🌵", "🍄", "🌻", "🍁"],
    "musica": ["🎸", "🎹", "🎷", "🥁", "🎧"],
}
CATEGORY_ORDER = list(POOLS)
COLORS = ["#5B5BD6", "#0F9D83", "#E8783A", "#D14D72", "#3976D2", "#7B61A8", "#B58A17"]
MAX_KEPT = 300


def fnv1a(text):
    h = 2166136261
    for ch in text:                       # igual que charCodeAt + Math.imul en JavaScript
        h ^= ord(ch) & 0xFFFF
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def make_piece(boot, n, categories):
    key = f"{boot}|{n}"
    seed = fnv1a(key)
    cats = [c for c in categories if c in POOLS] or ["trenes"]
    cat = cats[seed % len(cats)]
    pool = POOLS[cat]
    return {
        "id": key, "icon": pool[seed % len(pool)], "color": COLORS[(seed >> 3) % len(COLORS)],
        "category": cat, "date": int(time.time()),
    }


def collect(estado, token, rewards, categories):
    """Devuelve (rewards_nuevos, token_nuevo, piezas_ganadas). No modifica los argumentos."""
    try:
        boot = int(estado.get("idArranque"))
        count = int(estado.get("sesionesTrabajoCompletadas"))
    except (TypeError, ValueError, AttributeError):
        return rewards, token, []
    new_token = f"{boot}|{count}"
    if not token:                       # primera vez: solo se toma la referencia
        return rewards, new_token, []
    try:
        old_boot, old_count = (int(x) for x in str(token).split("|"))
    except ValueError:
        return rewards, new_token, []
    if boot != old_boot or count <= old_count:
        return rewards, new_token, []
    won = [make_piece(boot, n, categories) for n in range(old_count + 1, count + 1)]
    return (list(rewards) + won)[-MAX_KEPT:], new_token, won


def piece_name(piece, names):
    """Nombre de una pieza (p. ej. «Zorro») según su categoría e ícono; `names` = lista traducida en el orden de POOLS.
    Si la pieza no está en el catálogo (datos viejos) devuelve cadena vacía."""
    try:
        flat = [icon for cat in CATEGORY_ORDER for icon in POOLS[cat]]
        return names[flat.index(piece.get("icon"))]
    except (ValueError, IndexError, AttributeError, TypeError):
        return ""
