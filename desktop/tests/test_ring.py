"""El anillo del reloj se dibuja suavizado: bordes con transparencia parcial y tamaño estable."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ring_img  # noqa: E402


class RingTests(unittest.TestCase):
    def test_edges_are_antialiased_and_arc_follows_fraction(self):
        im = ring_img.render(102, 9, "#e6e6ee", "#5b5bd6", 0.5)
        self.assertEqual(im.size, (219, 219))
        hist = im.getchannel("A").histogram()
        self.assertGreater(sum(hist[1:255]), 200)                # medios tonos en el borde = sin dientes
        cx = im.width // 2
        right = im.getpixel((im.width - 4 - 4, im.height // 2))   # a las 3 en punto: dentro de la mitad pintada
        left = im.getpixel((4 + 4, im.height // 2))               # a las 9: solo la pista gris
        self.assertEqual(right[:3], (0x5b, 0x5b, 0xd6))
        self.assertEqual(left[:3], (0xe6, 0xe6, 0xee))
        self.assertEqual(im.getpixel((cx, im.height // 2))[3], 0)  # el centro está vacío

    def test_full_and_empty(self):
        full = ring_img.render(102, 9, "#e6e6ee", "#5b5bd6", 1.0)
        self.assertEqual(full.getpixel((full.width - 8, full.height // 2))[:3], (0x5b, 0x5b, 0xd6))
        empty = ring_img.render(102, 9, "#e6e6ee", "#5b5bd6", 0.0)
        self.assertEqual(empty.getpixel((empty.width - 8, empty.height // 2))[:3], (0xe6, 0xe6, 0xee))


if __name__ == "__main__":
    unittest.main()
