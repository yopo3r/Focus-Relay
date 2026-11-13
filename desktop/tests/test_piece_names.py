"""Cada pieza de colección tiene nombre en todos los idiomas (se muestra al pasar el mouse)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import i18n  # noqa: E402
import rewards  # noqa: E402


class PieceNameTests(unittest.TestCase):
    def test_every_piece_has_a_name_in_every_language(self):
        total = sum(len(v) for v in rewards.POOLS.values())
        for lang in i18n.LANGUAGES if hasattr(i18n, "LANGUAGES") else ("es", "en", "fr", "pt", "zh", "de", "it", "nl", "ru", "ja", "ko"):
            i18n.set_language(lang)
            names = i18n.get("piezaNombres")
            self.assertEqual(len(names), total, lang)
            self.assertEqual(len(set(names)), total, lang)                 # sin nombres repetidos
            for cat in rewards.CATEGORY_ORDER:
                for icon in rewards.POOLS[cat]:
                    self.assertTrue(rewards.piece_name({"icon": icon, "category": cat}, names), (lang, icon))
        i18n.set_language("es")

    def test_known_names_and_unknown_piece(self):
        i18n.set_language("es")
        names = i18n.get("piezaNombres")
        self.assertEqual(rewards.piece_name({"icon": "🦊"}, names), "Zorro")
        self.assertEqual(rewards.piece_name({"icon": "🚀"}, names), "Cohete")
        self.assertEqual(rewards.piece_name({"icon": "🦄"}, names), "")
        self.assertEqual(rewards.piece_name(None, names), "")


if __name__ == "__main__":
    unittest.main()
