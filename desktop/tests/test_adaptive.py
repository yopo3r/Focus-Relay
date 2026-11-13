import unittest
from datetime import datetime, timedelta

import adaptive
import calendar_planner as cp

NOW = datetime(2026, 11, 7, 18, 0)


def sess(days_ago, hour, minutes, ok, tag=""):
    end = (NOW - timedelta(days=days_ago)).replace(hour=hour, minute=0) + timedelta(minutes=minutes)
    e = {"duracion_seg": minutes * 60, "modo": "T", "epoch": int(end.timestamp()), "completada": ok}
    if tag:
        e["actividad"] = tag
    return e


def good_log():
    log = []
    for d in range(1, 11):
        log += [sess(d, 9, 40, True, "Cálculo"), sess(d, 10, 40, True), sess(d, 16, 40, True)]
    return log


class AdaptiveTests(unittest.TestCase):
    def test_not_ready_changes_nothing(self):
        p = adaptive.analyze([sess(1, 9, 30, True)] * 3, {}, NOW)
        self.assertFalse(p["ready"])
        self.assertEqual(adaptive.hour_scores(p), {})
        self.assertIsNone(adaptive.recommended_minutes(p))
        self.assertEqual(adaptive.tips(p)[0][0], "adTipPoco")

    def test_duration_and_hours(self):
        p = adaptive.analyze(good_log(), {}, NOW)
        self.assertTrue(p["ready"])
        self.assertEqual(adaptive.recommended_minutes(p), 40)
        self.assertEqual(p["best_hours"][0], 9)
        self.assertEqual(adaptive.estimate_for(p, "Cálculo"), 40)

    def test_short_when_cutting(self):
        log = [sess(d, 9, 20, False) for d in range(1, 8)] + [sess(d, 10, 45, True) for d in range(1, 6)]
        p = adaptive.analyze(log, {}, NOW)
        self.assertLess(p["duration"], 45)
        self.assertEqual(adaptive.tips(p)[0][0], "adTipDuracionCorta")

    def test_goal_rules(self):
        p = adaptive.analyze(good_log(), {"goal_daily_min": 300}, NOW)
        self.assertEqual(p["goal"]["kind"], "lower")
        p = adaptive.analyze(good_log(), {"goal_daily_min": 60}, NOW)
        self.assertEqual(p["goal"]["kind"], "raise")
        p = adaptive.analyze(good_log(), {}, NOW)
        self.assertEqual(p["goal"]["kind"], "set")

    def test_skipped_breaks(self):
        log = good_log() + [{"duracion_seg": 300, "modo": "D", "epoch": int((NOW - timedelta(days=d)).timestamp()),
                             "completada": False} for d in range(1, 7)]
        self.assertGreaterEqual(adaptive.analyze(log, {}, NOW)["skip_breaks"], 50)

    def test_fatigue(self):
        log = []
        for d in range(1, 8):
            log += [sess(d, 8, 30, True), sess(d, 10, 30, True), sess(d, 12, 30, True), sess(d, 15, 30, False)]
        for h in (8, 10, 12):                                    # hoy ya hizo 3
            log.append(sess(0, h, 30, True))
        p = adaptive.analyze(log, {}, NOW)
        self.assertEqual(p["fatigue_after"], 3)
        self.assertTrue(p["fatigue_now"])
        self.assertEqual(adaptive.fatigue_notice(p)[0], "adAvisoCansancio")

    def test_planner_prefers_best_hour(self):
        cfg = cp.PlannerConfig(day_start=8, day_end=20, hour_scores={9: 0.2, 15: 1.0})
        start = datetime(2026, 11, 9, 8, 0)
        self.assertEqual(cp._best_start(start, start.replace(hour=20), cfg).hour, 15)
        self.assertEqual(cp._best_start(start, start.replace(hour=20), cp.PlannerConfig()).hour, 8)


if __name__ == "__main__":
    unittest.main()
