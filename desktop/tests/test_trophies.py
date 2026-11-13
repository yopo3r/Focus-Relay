import unittest

import trophies


def sess(epoch, modo="T", dur=1500, done=True):
    return {"epoch": epoch, "modo": modo, "duracion_seg": dur, "completada": done}


class TrophyTests(unittest.TestCase):
    def test_earns_piece(self):
        self.assertTrue(trophies.earns_piece(sess(1)))
        self.assertFalse(trophies.earns_piece(sess(1, done=False)))
        self.assertFalse(trophies.earns_piece(sess(1, "D")))
        self.assertTrue(trophies.earns_piece(sess(1, "C", 900, None)))
        self.assertFalse(trophies.earns_piece(sess(1, "C", 899, None)))

    def test_timer_needs_five_minutes(self):
        self.assertFalse(trophies.earns_piece(sess(1, "T", 299)))
        self.assertTrue(trophies.earns_piece(sess(1, "T", 300)))
        self.assertFalse(trophies.earns_piece(sess(1, "W", 120)))
        self.assertTrue(trophies.earns_piece(sess(1, "W", 1500)))

    def test_award_is_idempotent(self):
        data = {"rewards": [], "rewarded": []}
        log = [sess(100), sess(200, "W"), sess(300, done=False)]
        self.assertEqual(len(trophies.award_from_log(log, data, ["trenes"])), 2)
        self.assertEqual(trophies.award_from_log(log, data, ["trenes"]), [])
        self.assertEqual(len(data["rewards"]), 2)

    def test_achievements_baseline_then_new(self):
        data = {}
        tot = {"best_streak": 3, "hours": 0, "sessions": 0, "tasks": 0, "longest_min": 0}
        self.assertEqual(trophies.check_achievements(tot, data), [])      # primera vez: sin avisos
        self.assertIn("streak_3", data["achievements"])
        tot["best_streak"] = 7
        self.assertEqual([a["id"] for a in trophies.check_achievements(tot, data)], ["streak_7"])
        self.assertEqual(trophies.check_achievements(tot, data), [])

    def test_progress_sections(self):
        tot = {"best_streak": 8, "hours": 12.0, "sessions": 3, "tasks": 0, "longest_min": 50}
        prog = dict(trophies.progress(tot))
        self.assertEqual(list(prog), ["streak", "focus", "tasks", "length"])
        self.assertEqual(prog["streak"][0][3], 14)
        self.assertEqual(len(prog["focus"]), 2)


if __name__ == "__main__":
    unittest.main()
