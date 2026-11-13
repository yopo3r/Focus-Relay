"""Anillo del reloj con bordes suaves.

El `create_arc` / `create_oval` de Tkinter no tiene suavizado y en Linux se ve dentado. Aquí el anillo se
dibuja con Pillow a 4× de resolución y se reduce (antialiasing); solo cambia la apariencia, no la lógica.
"""
import math

try:
    from PIL import Image, ImageDraw
    HAVE_PIL = True
except Exception:                       # pragma: no cover - sin Pillow se usa el dibujo de Tkinter
    HAVE_PIL = False
try:
    from PIL import ImageTk
except Exception:                       # pragma: no cover - sin tkinter (pruebas): solo se puede usar render()
    ImageTk = None

SCALE = 3
_cache = {}


def _rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def render(r, tw, track, arc, frac):
    """Imagen RGBA del anillo: pista `track` completa y arco `arc` que cubre `frac` (0 a 1) desde las 12 en punto."""
    pad = 3
    size = int(2 * r + tw) + 2 * pad
    big = size * SCALE
    c = big / 2
    outer = (r + tw / 2) * SCALE
    width = max(1, round(tw * SCALE))
    box = (c - outer, c - outer, c + outer, c + outer)

    track_mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(track_mask).ellipse(box, outline=255, width=width)

    arc_mask = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(arc_mask)
    frac = max(0.0, min(1.0, frac))
    if frac >= 0.999:
        d.ellipse(box, outline=255, width=width)
    elif frac > 0.0005:
        end = -90 + 360 * frac
        d.arc(box, start=-90, end=end, fill=255, width=width)
        cap = tw * SCALE / 2
        mid = r * SCALE
        for ang in (-90, end):                       # tapas redondeadas en los dos extremos
            x, y = c + mid * math.cos(math.radians(ang)), c + mid * math.sin(math.radians(ang))
            d.ellipse((x - cap, y - cap, x + cap, y + cap), fill=255)

    def layer(mask, color):
        im = Image.new("RGBA", (size, size), _rgb(color) + (0,))
        im.putalpha(mask.resize((size, size), Image.LANCZOS))     # solo el alfa se suaviza: el color no se mancha
        return im

    return Image.alpha_composite(layer(track_mask, track), layer(arc_mask, arc))


def photo(r, tw, track, arc, frac):
    """PhotoImage listo para `canvas.create_image` (con caché: el reloj repinta cada segundo). None sin Pillow."""
    if not HAVE_PIL or ImageTk is None:
        return None
    key = (r, tw, track, arc, int(frac * 720))
    if key not in _cache:
        if len(_cache) > 24:
            _cache.clear()
        _cache[key] = ImageTk.PhotoImage(render(r, tw, track, arc, frac))
    return _cache[key]
