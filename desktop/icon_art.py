"""Ícono de Focus Relay: cuadrado redondeado con degradado y un temporizador (anillo de progreso + aguja).

draw(size, a, b, fg) devuelve una imagen PIL RGBA. Se usa para el ícono de la app (assets/),
las ventanas y la bandeja. Se dibuja a 4x y se reduce para obtener bordes suaves.
"""
import math
from PIL import Image, ImageDraw

DEFAULT_A, DEFAULT_B, DEFAULT_FG = "#252d57", "#7b61d9", "#ffffff"


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def draw(size=256, a=DEFAULT_A, b=DEFAULT_B, fg=DEFAULT_FG):
    k = 4
    S = size * k
    ca, cb, cf = _rgb(a), _rgb(b), _rgb(fg)
    # degradado diagonal
    grad = Image.new("RGB", (S, S))
    px = grad.load()
    for y in range(S):
        for x in range(S):
            t = (x * 0.45 + y * 0.55) / S
            px[x, y] = tuple(round(p + (q - p) * t) for p, q in zip(ca, cb))
    mask = Image.new("L", (S, S), 0)
    m = int(S * 0.04)
    ImageDraw.Draw(mask).rounded_rectangle((m, m, S - m, S - m), radius=int(S * 0.23), fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    # brillo suave arriba
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-S * 0.4, -S * 0.9, S * 1.4, S * 0.38), fill=cf + (16,))
    glow = Image.composite(glow, Image.new("RGBA", (S, S), (0, 0, 0, 0)), mask)
    img = Image.alpha_composite(img, glow)

    d = ImageDraw.Draw(img, "RGBA")
    cx = cy = S / 2
    r, w = S * 0.255, S * 0.058
    box = (cx - r, cy - r, cx + r, cy + r)
    d.ellipse(box, outline=cf + (70,), width=int(w))                       # pista
    d.arc(box, start=-90, end=200, fill=cf + (255,), width=int(w))          # progreso (~80 %)
    for ang in (-90, 200):                                                 # extremos redondeados
        ex, ey = cx + r * math.cos(math.radians(ang)), cy + r * math.sin(math.radians(ang))
        d.ellipse((ex - w / 2, ey - w / 2, ex + w / 2, ey + w / 2), fill=cf + (255,))
    # aguja hacia el extremo del arco + centro
    hl = r * 0.62
    hx, hy = cx + hl * math.cos(math.radians(200)), cy + hl * math.sin(math.radians(200))
    d.line((cx, cy, hx, hy), fill=cf + (255,), width=int(w * 0.7))
    d.ellipse((hx - w * 0.35, hy - w * 0.35, hx + w * 0.35, hy + w * 0.35), fill=cf + (255,))
    d.ellipse((cx - w * 0.7, cy - w * 0.7, cx + w * 0.7, cy + w * 0.7), fill=cf + (255,))
    # botón superior del cronómetro
    d.rounded_rectangle((cx - w * 0.7, cy - r - w * 2.3, cx + w * 0.7, cy - r - w * 1.25), radius=int(w * 0.3), fill=cf + (255,))
    return img.resize((size, size), Image.LANCZOS)


def save_assets(folder):
    import os
    os.makedirs(folder, exist_ok=True)
    base = draw(512)
    base.save(os.path.join(folder, "icon.png"))
    draw(256).save(os.path.join(folder, "icon-256.png"))
    draw(64).save(os.path.join(folder, "icon-64.png"))
    draw(256).save(os.path.join(folder, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    import os
    save_assets(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"))
