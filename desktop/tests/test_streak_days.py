import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import insights  # noqa: E402
import stats  # noqa: E402

WEEKDAYS = (0, 1, 2, 3, 4)
MON = date(2026, 11, 9)          # lunes


def days(*offsets):
    return {MON + timedelta(days=o): 1 for o in offsets}


class StreakDaysTests(unittest.TestCase):
    def test_default_all_days_unchanged(self):
        self.assertEqual(stats.streak(days(0, 1, 2), MON + timedelta(days=2)), 3)
        self.assertEqual(stats.streak(days(0, 2), MON + timedelta(days=2)), 1)   # el martes cortó

    def test_weekend_does_not_break_weekday_streak(self):
        # lun-vie de la semana anterior + lun-mar actual; sáb y dom sin sesión
        counts = days(-7, -6, -5, -4, -3, 0, 1)
        self.assertEqual(stats.streak(counts, MON + timedelta(days=1), WEEKDAYS), 7)
        self.assertEqual(stats.streak(counts, MON + timedelta(days=1)), 2)       # con todos los días sí se pierde

    def test_missing_workday_breaks(self):
        counts = days(-7, -6, -4, -3, 0, 1)                                     # falta el miércoles anterior
        self.assertEqual(stats.streak(counts, MON + timedelta(days=1), WEEKDAYS), 4)

    def test_working_on_a_free_day_counts(self):
        counts = days(-2, -1, 0)                                                # sáb, dom y lunes
        self.assertEqual(stats.streak(counts, MON, WEEKDAYS), 3)

    def test_today_not_yet_worked_counts_from_yesterday(self):
        counts = days(-3, 0)                                                    # viernes y lunes; hoy martes aún nada
        self.assertEqual(stats.streak(counts, MON + timedelta(days=1), WEEKDAYS), 2)

    def test_today_free_day_without_session_keeps_streak(self):
        counts = days(-3)                                                       # viernes; hoy domingo sin sesión
        self.assertEqual(stats.streak(counts, MON - timedelta(days=1), WEEKDAYS), 1)

    def test_empty_and_terminates(self):
        self.assertEqual(stats.streak({}, MON, WEEKDAYS), 0)
        self.assertEqual(stats.streak({}, MON, (6,)), 0)

    def test_best_streak_with_days(self):
        counts = days(-7, -6, -5, -4, -3, 0, 1)
        self.assertEqual(insights.best_streak(counts, WEEKDAYS), 7)
        self.assertEqual(insights.best_streak(counts), 5)

    def test_streak_days_config_parsing(self):
        self.assertEqual(stats.streak_days({}), (0, 1, 2, 3, 4, 5, 6))
        self.assertEqual(stats.streak_days({"streak_days": [4, 0, 0, 9]}), (0, 4))
        self.assertEqual(stats.streak_days({"streak_days": []}), (0, 1, 2, 3, 4, 5, 6))
        self.assertEqual(stats.streak_days({"streak_days": "x"}), (0, 1, 2, 3, 4, 5, 6))


if __name__ == "__main__":
    unittest.main()
