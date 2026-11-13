import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import updates  # noqa: E402


class UpdatesTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(updates.parse_version("v3.21.2"), (3, 21, 2))
        self.assertEqual(updates.parse_version("3.21.2-beta"), (3, 21, 2))
        self.assertEqual(updates.parse_version(""), ())

    def test_is_newer(self):
        self.assertTrue(updates.is_newer("v3.22.0", "3.21.2"))
        self.assertTrue(updates.is_newer("4.0", "3.21.2"))
        self.assertFalse(updates.is_newer("v3.21.2", "3.21.2"))
        self.assertFalse(updates.is_newer("v3.9.0", "3.21.2"))     # 9 < 21 numéricamente, no como texto
        self.assertFalse(updates.is_newer("", "3.21.2"))

    def test_urls_point_to_repo(self):
        for u in (updates.REPO_URL, updates.BUG_URL, updates.IDEA_URL, updates.RELEASES_URL):
            self.assertIn("github.com/yopo3r/Focus-Relay", u)


if __name__ == "__main__":
    unittest.main()
