"""El sonido de aviso se sintetiza bien: duración razonable, sin recortes y con el volumen pedido."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chime  # noqa: E402


class ChimeTests(unittest.TestCase):
    def test_every_kind_is_short_and_not_clipped(self):
        for kind in chime.KINDS:
            buf = chime.samples(kind, 1.0)
            secs = len(buf) / 2 / chime.RATE
            self.assertTrue(1.0 < secs < 4.0, kind)
            self.assertLess(max(abs(x) for x in buf), 32767 * 0.81, kind)
            self.assertEqual(buf[-1], 0)                      # termina en silencio: sin chasquido

    def test_volume_scales_and_zero_is_silent(self):
        loud = max(chime.samples("done", 1.0))
        soft = max(chime.samples("done", 0.25))
        self.assertAlmostEqual(soft / loud, 0.25, delta=0.02)
        self.assertEqual(max(chime.samples("done", 0.0)), 0)
        self.assertFalse(chime.play("done", 0))


if __name__ == "__main__":
    unittest.main()
