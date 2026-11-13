"""Terminar antes de tiempo: aviso simple, modo estricto (1 a 100 confirmaciones) y límites de la configuración."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
import guard  # noqa: E402

TIMER = {"ejecutando": True, "modo": "T", "fase": "-"}
WORK = {"ejecutando": True, "modo": "P", "fase": "W"}
BREAK = {"ejecutando": True, "modo": "P", "fase": "D"}
CHRONO = {"ejecutando": True, "modo": "C", "fase": "-"}
IDLE = {"ejecutando": False, "modo": "T", "fase": "-"}


class GuardTests(unittest.TestCase):
    def test_simple_warning(self):
        self.assertEqual(guard.confirmations_needed({"confirm_stop": True}, TIMER), 1)
        self.assertEqual(guard.confirmations_needed({"confirm_stop": False}, TIMER), 0)

    def test_strict_uses_configured_count_and_ignores_the_simple_setting(self):
        cfg = {"strict_mode": True, "strict_confirms": 7, "confirm_stop": False}
        self.assertEqual(guard.confirmations_needed(cfg, TIMER), 7)
        self.assertEqual(guard.confirmations_needed(cfg, WORK), 7)

    def test_only_focus_sessions_are_protected(self):
        cfg = {"strict_mode": True, "strict_confirms": 5}
        for est in (BREAK, CHRONO, IDLE, None):
            self.assertEqual(guard.confirmations_needed(cfg, est), 0)

    def test_count_is_clamped_to_1_100(self):
        for raw, want in ((0, 1), (-4, 1), (1, 1), (100, 100), (101, 100), (9999, 100), ("12", 12), (" 8 ", 8)):
            self.assertEqual(guard.clamp_confirms(raw), want)
        self.assertEqual(guard.clamp_confirms("abc", 3), 3)
        self.assertEqual(guard.clamp_confirms(None, 3), 3)

    def test_strict_settings_are_locked_during_a_session(self):
        cfg = {"strict_mode": True}
        for est in (TIMER, WORK, BREAK):                      # también durante el descanso del Pomodoro
            self.assertTrue(guard.settings_locked(cfg, est))
        for est in (IDLE, CHRONO, None):
            self.assertFalse(guard.settings_locked(cfg, est))
        self.assertFalse(guard.settings_locked({"strict_mode": False}, TIMER))

    def test_unlock_code_is_random_readable_and_forgiving(self):
        codes = {guard.new_code() for _ in range(200)}
        self.assertGreater(len(codes), 190)                   # distinto cada vez
        for c in codes:
            self.assertRegex(c, r"^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$")
        self.assertTrue(guard.code_matches("K7QM-4TXD", "k7qm4txd"))
        self.assertTrue(guard.code_matches("K7QM-4TXD", " K7QM 4TXD "))
        self.assertFalse(guard.code_matches("K7QM-4TXD", "K7QM-4TXE"))
        self.assertFalse(guard.code_matches("K7QM-4TXD", ""))
        self.assertFalse(guard.code_matches("", ""))

    def test_config_defaults_and_migration(self):
        self.assertFalse(config.DEFAULT_CONFIG["strict_mode"])
        self.assertFalse(config.DEFAULT_CONFIG["minimize_on_task"])
        self.assertEqual(config.migrate({"strict_confirms": 500})["strict_confirms"], 100)
        self.assertEqual(config.migrate({"strict_confirms": 0})["strict_confirms"], 1)
        self.assertEqual(config.migrate({"strict_confirms": "x"})["strict_confirms"], 3)


if __name__ == "__main__":
    unittest.main()


class BlockLockTests(unittest.TestCase):
    def test_block_settings_locked(self):
        import guard
        self.assertTrue(guard.block_settings_locked({"ejecutando": True, "modo": "P", "fase": "D"}))
        self.assertTrue(guard.block_settings_locked({"ejecutando": True, "modo": "T"}))
        self.assertFalse(guard.block_settings_locked({"ejecutando": True, "modo": "C"}))
        self.assertFalse(guard.block_settings_locked({"ejecutando": False, "modo": "T"}))
        self.assertFalse(guard.block_settings_locked(None))

    def test_chrono_lock_depends_on_setting(self):
        est = {"ejecutando": True, "modo": "C"}
        self.assertFalse(guard.block_settings_locked(est, {}))
        self.assertTrue(guard.block_settings_locked(est, {"block_in_chrono": True}))

    def test_quit_locked(self):
        on = {"strict_mode": True}
        for modo in ("T", "P", "C"):
            self.assertTrue(guard.quit_locked(on, {"ejecutando": True, "modo": modo}))
        self.assertFalse(guard.quit_locked(on, {"ejecutando": False, "modo": "T"}))
        self.assertFalse(guard.quit_locked(on, None))
        self.assertFalse(guard.quit_locked({"strict_mode": False}, {"ejecutando": True, "modo": "T"}))
