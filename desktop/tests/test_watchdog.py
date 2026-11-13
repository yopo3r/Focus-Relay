import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import watchdog  # noqa: E402


class _Root:
    def after(self, ms, fn):
        pass                      # el hilo de la interfaz «está colgado»: nunca vuelve a latir


class WatchdogTests(unittest.TestCase):
    def test_dump_written_when_ui_stalls(self):
        with tempfile.TemporaryDirectory() as d:
            path = watchdog.log_path(d)
            w = watchdog.Watchdog(_Root(), path, limit=0.2, poll=0.1, version="x").start()
            time.sleep(0.9)
            w.stop()
            text = open(path, encoding="utf-8").read()
            self.assertIn("no responde", text)
            self.assertIn("Thread", text)
            self.assertEqual(text.count("no responde"), 1)       # un solo informe por cuelgue

    def test_no_dump_when_alive(self):
        class Live(_Root):
            def after(self, ms, fn):
                fn()
        with tempfile.TemporaryDirectory() as d:
            w = watchdog.Watchdog(Live(), watchdog.log_path(d), limit=0.5, poll=0.1)
            w._beat()
            self.assertFalse(w.stalled())


if __name__ == "__main__":
    unittest.main()
