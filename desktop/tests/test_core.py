"""Pruebas de la lógica pura (sin ventanas). Ejecutar:  python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
_TMP = tempfile.mkdtemp()
os.environ["XDG_CONFIG_HOME"] = _TMP          # nunca tocar la configuración real
os.environ["APPDATA"] = _TMP

import backup  # noqa: E402
import i18n  # noqa: E402
import re  # noqa: E402
import config  # noqa: E402
import stats  # noqa: E402
import tasks  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_migrate_bad_values(self):
        c = config.migrate({"goal_daily_min": "x", "warn_end_min": 999, "text_scale": "y"})
        self.assertEqual((c["goal_daily_min"], c["warn_end_min"], c["text_scale"]), (0, 60, 1.0))
        self.assertEqual(c["schema_version"], config.SCHEMA_VERSION)

    def test_load_non_dict(self):
        self.assertIsInstance(config.migrate(dict(config.DEFAULT_CONFIG)), dict)


class StatsTests(unittest.TestCase):
    def test_goal_progress_ignores_breaks(self):
        now = datetime(2026, 11, 4, 15, 0)
        ep = lambda h: (now.replace(hour=h)).timestamp()      # noqa: E731
        log = [{"epoch": ep(9), "duracion_seg": 1800, "modo": "T"},
               {"epoch": ep(10), "duracion_seg": 300, "modo": "D"},
               {"epoch": (now - timedelta(days=1)).timestamp(), "duracion_seg": 600, "modo": "T"}]
        prog = dict((k, (d, g)) for k, d, g in stats.goal_progress(log, {"goal_daily_min": 60, "goal_weekly_min": 0}, now))
        self.assertEqual(prog, {"day": (30, 60)})

    def test_no_goals(self):
        self.assertEqual(stats.goal_progress([], {}, datetime.now()), [])


class BackupTests(unittest.TestCase):
    def test_roundtrip_keeps_secret_out_and_local_url(self):
        cfg = config.load_config()
        cfg["calendar_url"] = "https://secreto"
        config.save_config(cfg)
        z = os.path.join(_TMP, "b.zip")
        backup.export_zip(z)
        self.assertNotIn("secreto", zipfile.ZipFile(z).read("config.json").decode())
        backup.restore_zip(z)
        self.assertEqual(config.load_config()["calendar_url"], "https://secreto")

    def test_rejects_garbage(self):
        bad = os.path.join(_TMP, "bad.zip")
        open(bad, "wb").write(b"no soy un zip")
        with self.assertRaises(ValueError):
            backup.inspect(bad)
        evil = os.path.join(_TMP, "evil.zip")
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../../evil.py", "print(1)")
        with self.assertRaises(ValueError):                    # nada reconocible: se rechaza
            backup.inspect(evil)

    def test_rejects_corrupt_json(self):
        p = os.path.join(_TMP, "c.zip")
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("data.json", "{roto")
        with self.assertRaises(ValueError):
            backup.inspect(p)


class TaskTests(unittest.TestCase):
    def test_add_and_done(self):
        d = tasks.load()
        n = len(d["items"])
        item = tasks.add_task(d, "Probar")
        self.assertEqual(len(d["items"]), n + 1)
        tasks.set_done(d, item["id"], True)
        self.assertTrue([i for i in d["items"] if i["id"] == item["id"]][0]["done"])

    def test_corrupt_file_is_survivable(self):
        open(tasks.path() if callable(getattr(tasks, "path", None)) else os.path.join(config.config_dir(), "tasks.json"),
             "w").write("{no json")
        self.assertIsInstance(tasks.load(), dict)


class LocaleTests(unittest.TestCase):
    """Cada idioma debe tener todas las claves, la misma estructura y los mismos {marcadores}."""
    PH = re.compile(r"\{\w*\}")

    def _same(self, a, b, where):
        if isinstance(a, str):
            self.assertIsInstance(b, str, where)
            self.assertTrue(b.strip(), where)
            self.assertEqual(sorted(self.PH.findall(a)), sorted(self.PH.findall(b)), where)
        else:
            self.assertEqual(len(a), len(b), where)
            for i, (x, y) in enumerate(zip(a, b)):
                self._same(x, y, f"{where}[{i}]")

    def test_all_languages_complete(self):
        i18n._load_web()
        base = {k: v[0] for k, v in i18n.NEW.items()}
        base.update({k: v for k, v in i18n._web["es"].items() if k not in base})
        for code, _name in i18n.LANGS:
            if code in i18n.BASE:
                continue
            table = i18n._load_extra(code)
            self.assertEqual(set(table), set(base), code)
            for key, ref in base.items():
                self._same(ref, table[key], f"{code}:{key}")

    def test_months_and_dates(self):
        import datetime
        for code, _name in i18n.LANGS:
            i18n.set_language(code)
            self.assertEqual(len(i18n.MONTHS[code]), 12)
            self.assertTrue(i18n.date_label(datetime.date(2026, 11, 5)))
            self.assertTrue(i18n.month_label(2026, 11))
            datetime.datetime(2026, 11, 5, 14, 3, 9).strftime(i18n.locale_date_format())
        i18n.set_language("es")


if __name__ == "__main__":
    unittest.main()


class StatsFixesTests(unittest.TestCase):
    def test_week_summary_ignores_breaks(self):
        import stats
        from datetime import datetime
        now = datetime.now()
        log = [{"modo": "W", "duracion_seg": 1500, "epoch": int(now.timestamp())},
               {"modo": "D", "duracion_seg": 300, "epoch": int(now.timestamp())}]
        self.assertEqual(stats.week_summary(log, now), (1, 25))

    def test_csv_formula_injection(self):
        import stats
        out = stats.export_csv([{"modo": "T", "duracion_seg": 60, "actividad": "=HYPERLINK(1)"}], "h", lambda m: m, "-")
        self.assertIn("'=HYPERLINK(1)", out)
