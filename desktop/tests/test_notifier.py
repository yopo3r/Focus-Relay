"""Notificaciones en Linux: se usa el servicio del escritorio (notify-send / gdbus), no pystray."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import notifier  # noqa: E402


def fake_run(returns):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        code = returns.get(os.path.basename(cmd[0]), 1)
        return mock.Mock(returncode=code, stdout="(true,)", stderr="")
    return run, calls


class NotifierTests(unittest.TestCase):
    def test_notify_send_is_preferred_and_safe_with_dashes(self):
        run, calls = fake_run({"notify-send": 0})
        with mock.patch("notifier.shutil.which", side_effect=lambda n: "/usr/bin/" + n), \
                mock.patch("notifier.subprocess.run", run):
            self.assertTrue(notifier.send_linux("-título", "cuerpo"))
        self.assertEqual(calls[0][0], "notify-send")
        self.assertIn("--", calls[0])
        self.assertEqual(calls[0][-2:], ["-título", "cuerpo"])

    def test_falls_back_to_gdbus_then_reports_failure(self):
        run, calls = fake_run({"notify-send": 1, "gdbus": 0})
        with mock.patch("notifier.shutil.which", side_effect=lambda n: "/usr/bin/" + n), \
                mock.patch("notifier.subprocess.run", run):
            self.assertTrue(notifier.send_linux("t", "m"))
        self.assertEqual([c[0] for c in calls], ["notify-send", "gdbus"])
        run, _ = fake_run({"notify-send": 1, "gdbus": 1})
        with mock.patch("notifier.shutil.which", side_effect=lambda n: "/usr/bin/" + n), \
                mock.patch("notifier.subprocess.run", run):
            self.assertFalse(notifier.send_linux("t", "m"))

    def test_tray_is_only_a_last_resort_on_linux(self):
        tray = mock.Mock()
        with mock.patch("notifier.IS_LINUX", True), mock.patch("notifier.send_linux", return_value=True):
            self.assertTrue(notifier.send("t", "m", tray))
        tray.notify.assert_not_called()
        with mock.patch("notifier.IS_LINUX", True), mock.patch("notifier.send_linux", return_value=False):
            self.assertTrue(notifier.send("t", "m", tray))
        tray.notify.assert_called_once()

    def test_send_never_raises(self):
        tray = mock.Mock()
        tray.notify.side_effect = NotImplementedError
        with mock.patch("notifier.IS_LINUX", True), mock.patch("notifier.send_linux", return_value=False):
            self.assertFalse(notifier.send("t", "m", tray))


if __name__ == "__main__":
    unittest.main()
