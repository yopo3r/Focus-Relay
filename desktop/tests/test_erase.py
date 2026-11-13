import os
import stat
import sys
import tempfile
import unittest

_TMP = tempfile.mkdtemp()
os.environ["XDG_CONFIG_HOME"] = _TMP
os.environ["APPDATA"] = _TMP
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backup  # noqa: E402
import config  # noqa: E402


class EraseTests(unittest.TestCase):
    def test_erase_all_removes_data_but_keeps_lock(self):
        base = config.config_dir()
        for name in ("config.json", "data.json", "tasks.json", "local_sessions.json", "calendar.ics",
                     "hang.log", "config.json.bak", "app.lock"):
            with open(os.path.join(base, name), "w") as f:
                f.write("x")
        n = backup.erase_all()
        self.assertEqual(n, 7)
        self.assertEqual(os.listdir(base), ["app.lock"])

    @unittest.skipIf(sys.platform.startswith("win"), "permisos POSIX")
    def test_config_dir_is_private(self):
        mode = stat.S_IMODE(os.stat(config.config_dir()).st_mode)
        self.assertEqual(mode, 0o700)


if __name__ == "__main__":
    unittest.main()
