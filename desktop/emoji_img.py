"""Emoji a color como imagen (Tkinter no los dibuja bien en todos los sistemas).

Usa una fuente de emoji a color del sistema con Pillow. Si no encuentra ninguna, devuelve
None y la interfaz muestra el emoji como texto.
"""
import os

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    HAVE_PIL = True
except Exception:                       # pragma: no cover
    HAVE_PIL = False

_CANDIDATES = [
    ("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109),
    ("/usr/share/fonts/noto/NotoColorEmoji.ttf", 109),
    ("/usr/share/fonts/google-noto-emoji/NotoColorEmoji.ttf", 109),
    (r"C:\Windows\Fonts\seguiemj.ttf", 109),
    ("/System/Library/Fonts/Apple Color Emoji.ttc", 160),
]
_font = {"obj": None, "tried": False}
_cache = {}


def _load_font():
    if not _font["tried"]:
        _font["tried"] = True
        for path, size in _CANDIDATES:
            if os.path.exists(path):
                try:
                    _font["obj"] = ImageFont.truetype(path, size)
                    break
                except Exception:
                    continue
    return _font["obj"]


def _glyph(font, emoji):
    """Recorte del emoji dibujado a tamaño completo. Si el motor de texto avanzado (raqm) lo deja en blanco —pasa con
    algunos emoji según la versión de FreeType/raqm—, se reintenta con el motor básico."""
    engines = [font]
    try:
        engines.append(ImageFont.truetype(font.path, font.size, layout_engine=ImageFont.Layout.BASIC))
    except Exception:
        pass
    for f in engines:
        for text in (emoji, emoji.replace("\ufe0f", "")):          # algunos motores fallan con el selector de variación
            canvas = Image.new("RGBA", (f.size * 2, f.size * 2), (0, 0, 0, 0))
            ImageDraw.Draw(canvas).text((f.size // 2, f.size // 2), text, font=f, embedded_color=True)
            box = canvas.getbbox()
            if box and canvas.crop(box).getchannel("A").getextrema()[1] > 40:
                return canvas.crop(box)
    return None


def diagnose(icons):
    """Íconos que no se pueden dibujar como imagen (para `main.py --diagnose`)."""
    if not HAVE_PIL:
        return list(icons), "sin Pillow/ImageTk"
    if _load_font() is None:
        return list(icons), "sin fuente de emoji a color (instala fonts-noto-color-emoji)"
    return [i for i in icons if render(i, 22) is None], ""


def render(emoji, px):
    """PIL.Image RGBA de `px` x `px` con el emoji, o None si no hay fuente de emoji."""
    if not HAVE_PIL:
        return None
    font = _load_font()
    if font is None:
        return None
    key = (emoji, px)
    if key in _cache:
        return _cache[key]
    try:
        img = _glyph(font, emoji)
        if img is None:
            return None
        scale = px / max(img.size)
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
        out = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        out.paste(img, ((px - img.width) // 2, (px - img.height) // 2), img)
    except Exception:
        return None
    _cache[key] = out
    return out


def photo(emoji, px):
    """ImageTk.PhotoImage (hay que conservar la referencia) o None."""
    img = render(emoji, px)
    return ImageTk.PhotoImage(img) if img is not None else None
