import os
import tempfile
import time
import unittest
from unittest import mock

import local_timer


class LocalTimerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(local_timer, "log_path", lambda: os.path.join(self.tmp.name, "log.json"))
        p.start()
        self.addCleanup(p.stop)
        c = mock.patch.object(local_timer, "load_config", lambda: {"local_durations": {"pomTrabajo": 25, "pomDescanso": 5}})
        c.start()
        self.addCleanup(c.stop)
        self.eng = local_timer.LocalTimer()

    def _advance(self, seconds):
        """Mueve el reloj del motor hacia atrás (equivale a que pase `seconds` s)."""
        e = self.eng
        e.start_at -= seconds
        e.end_at -= seconds

    def test_timer_completes_and_logs(self):
        self.eng.start(10)
        self._advance(601)
        snap = self.eng.snapshot()
        self.assertFalse(snap["ejecutando"])
        log = self.eng._load_log()
        self.assertEqual(len(log), 1)
        self.assertEqual((log[0]["modo"], log[0]["duracion_seg"], log[0]["completada"]), ("T", 600, True))

    def test_pomodoro_moves_to_break(self):
        self.eng.set_mode("P")
        self.eng.start()
        self._advance(25 * 60 + 2)
        snap = self.eng.snapshot()
        self.assertTrue(snap["ejecutando"])
        self.assertEqual(snap["fase"], "D")

    def test_long_sleep_does_not_invent_sessions(self):
        self.eng.set_mode("P")
        self.eng.start()
        self._advance(8 * 3600)                      # el equipo durmió 8 horas
        self.eng.snapshot()
        log = self.eng._load_log()
        self.assertLessEqual(len(log), 1)
        self.assertFalse(self.eng.running)

    def test_short_session_not_logged(self):
        self.eng.start(5)
        time.sleep(0.01)
        self.eng.stop()
        self.assertEqual(self.eng._load_log(), [])

    def test_activity_is_cleared_after_finish(self):
        self.eng.start(5, "Cálculo")
        self._advance(301)
        self.eng.snapshot()
        self.assertEqual(self.eng.activity, "")
        self.assertEqual(self.eng._load_log()[0]["actividad"], "Cálculo")


if __name__ == "__main__":
    unittest.main()
