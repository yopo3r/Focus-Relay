import unittest

import sites


class IdnTests(unittest.TestCase):
    def test_idn_becomes_punycode(self):
        self.assertEqual(sites.normalize("https://www.ñandú.cl/x"), "xn--and-6ma2c.cl")

    def test_garbage_rejected(self):
        for bad in ("", "localhost", "a b.com", "http://", "..", "x" * 200 + ".com"):
            self.assertEqual(sites.normalize(bad), "")


class SitesTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(sites.normalize("https://www.YouTube.com/watch?v=1"), "youtube.com")
        self.assertEqual(sites.normalize("  Reddit.com:443/r/x "), "reddit.com")
        for bad in ("", "localhost", "no es un dominio", "javascript:alert(1)", "a" * 120 + ".com", None):
            self.assertEqual(sites.normalize(bad), "")

    def test_parse_and_add(self):
        self.assertEqual(sites.parse_list("youtube.com\nwww.x.com, youtube.com;;bad"), ["youtube.com", "x.com"])
        self.assertEqual(sites.add(["x.com"], "X.com"), (["x.com"], False))
        self.assertEqual(sites.add(["x.com"], "twitch.tv"), (["x.com", "twitch.tv"], True))

    def test_is_blocked(self):
        self.assertTrue(sites.is_blocked("m.youtube.com", ["youtube.com"], []))
        self.assertFalse(sites.is_blocked("music.youtube.com", ["youtube.com"], ["music.youtube.com"]))
        self.assertFalse(sites.is_blocked("notyoutube.com", ["youtube.com"], []))


if __name__ == "__main__":
    unittest.main()
