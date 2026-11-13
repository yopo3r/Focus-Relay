"""Cobertura de traducciones: todos los idiomas tienen las mismas claves, marcadores y estructura."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import i18n  # noqa: E402

PH = re.compile(r"\{\w+\}")


def shape(v):
    return [shape(x) for x in v] if isinstance(v, list) else "s"


class I18nTests(unittest.TestCase):
    def setUp(self):
        i18n._load_web()
        self.keys = set(i18n.NEW) | set(i18n._web["es"])

    def test_every_language_covers_every_key(self):
        for code, _name in i18n.LANGS:
            for key in self.keys:
                val = i18n.get(key, code)
                self.assertNotEqual(val, key, f"{code}: falta {key}")
                self.assertEqual(shape(val), shape(i18n.get(key, "es")), f"{code}: estructura de {key}")

    def test_placeholders_match_spanish(self):
        def flat(v):
            return [v] if isinstance(v, str) else [s for x in v for s in flat(x)]
        for code, _name in i18n.LANGS:
            for key in self.keys:
                ref = [sorted(PH.findall(s)) for s in flat(i18n.get(key, "es"))]
                got = [sorted(PH.findall(s)) for s in flat(i18n.get(key, code))]
                self.assertEqual(ref, got, f"{code}: marcadores de {key}")

    def test_dates_and_months(self):
        from datetime import date
        for code, _name in i18n.LANGS:
            i18n.set_language(code)
            self.assertTrue(i18n.date_label(date(2026, 11, 5)))
            self.assertIn("2026", i18n.month_label(2026, 11))
            self.assertTrue(i18n.locale_date_format())
            self.assertEqual(len(i18n.MONTHS[code]), 12)
        i18n.set_language("es")


if __name__ == "__main__":
    unittest.main()
