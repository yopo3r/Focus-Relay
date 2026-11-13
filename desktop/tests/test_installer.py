import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "packaging"))
import installer_gui as ig  # noqa: E402  (no importa tkinter hasta main())


class InstallerGuiTests(unittest.TestCase):
    def test_every_text_has_every_language(self):
        for key, row in ig._T.items():
            self.assertEqual(len(row), len(ig.LANGS), key)
            self.assertTrue(all(x.strip() for x in row), key)

    def test_detect_lang(self):
        self.assertEqual(ig.detect_lang({"LANG": "fr_FR.UTF-8"}), "fr")
        self.assertEqual(ig.detect_lang({"FR_LANG": "ja", "LANG": "es_CL"}), "ja")
        self.assertEqual(ig.tr("install", "xx"), "Install")

    def test_plan_follows_options(self):
        base = [k for k, _ in ig.plan({}, "/app", "py")]
        self.assertEqual(base, ["step_env", "step_deps", "step_links"])
        steps = dict(ig.plan({"startup": True, "tasks": True}, "/app", "py"))
        self.assertEqual(len(steps["step_startup"]), 2)
        self.assertIn("startup_tasks=True", steps["step_startup"][1][2])

    def test_shortcut_script_quotes_paths(self):
        s = ig.shortcut_script("C:\\Users\\O'Brien\\Focus", True)
        self.assertIn("O''Brien", s)
        self.assertIn("'Desktop'", s)
        self.assertNotIn("'Desktop'", ig.shortcut_script("C:\\x", False))


class LinuxScriptsTests(unittest.TestCase):
    def test_scripts_parse_and_translate(self):
        root = os.path.dirname(HERE)
        for rel in ("install_linux.sh", os.path.join("packaging", "install_linux_bundle.sh")):
            path = os.path.join(root, rel)
            self.assertEqual(subprocess.call(["bash", "-n", path]), 0, rel)
            text = open(path, encoding="utf-8").read()
            for code in ("es", "en", "fr", "pt", "de", "it", "nl", "ru", "ja", "ko", "zh"):
                if code != "en":
                    self.assertIn(f"    {code}:DONE)", text, (rel, code))


if __name__ == "__main__":
    unittest.main()
