import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import music  # noqa: E402
import services  # noqa: E402


class OfflineTests(unittest.TestCase):
    def test_has_internet_is_bounded_even_if_connections_hang(self):
        os.environ.pop("FOCUS_RELAY_OFFLINE", None)
        with mock.patch("socket.create_connection", side_effect=lambda *a, **k: time.sleep(8)):
            t0 = time.time()
            self.assertFalse(music.has_internet(timeout=0.5))
            self.assertLess(time.time() - t0, 2.0)

    def test_has_internet_true_when_any_probe_connects(self):
        os.environ.pop("FOCUS_RELAY_OFFLINE", None)
        sock = mock.Mock()
        with mock.patch("socket.create_connection", return_value=sock):
            self.assertTrue(music.has_internet(timeout=0.5))

    def test_open_with_deadline_gives_up(self):
        with mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: time.sleep(5)):
            t0 = time.time()
            with self.assertRaises(TimeoutError):
                music._open_with_deadline("https://example.invalid/x", 0.4)
            self.assertLess(time.time() - t0, 2.0)

    def test_collapse_keeps_music_command_over_checks(self):
        c = services.MusicController.collapse
        self.assertEqual(c([("play", "groove", 0.3), ("check", True)]), ("play", "groove", 0.3))
        self.assertEqual(c([("check", True), ("stop",)]), ("stop",))
        self.assertEqual(c([("check", False)]), ("check", False))

    def test_check_online_never_blocks_the_caller(self):
        ctl = services.MusicController()
        with mock.patch("music.has_internet", side_effect=lambda *a, **k: time.sleep(5)):
            t0 = time.time()
            ctl._last_check = 0
            ctl.check_online(True)
            self.assertLess(time.time() - t0, 0.5)


if __name__ == "__main__":
    unittest.main()
