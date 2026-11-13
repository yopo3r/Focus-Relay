import os
import tempfile
import unittest
from unittest import mock

import esp_client


class FakeEngine:
    def __init__(self, log):
        self.log, self.tagged = list(log), []

    def get_log(self):
        return [dict(s) for s in self.log]

    def clear_log(self):
        self.log = []
        return True

    def tag(self, i, activity):
        self.tagged.append((i, activity))
        return True


class UnifiedLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = FakeEngine([{"duracion_seg": 600, "modo": "T", "epoch": 200, "completada": True},
                                  {"duracion_seg": 900, "modo": "T", "epoch": 400, "completada": True}])
        for p in (mock.patch.object(esp_client, "_cache_path", lambda: os.path.join(self.tmp.name, "c.json")),
                  mock.patch.object(esp_client, "_local", lambda: types_ns(ENGINE=self.engine))):
            p.start()
            self.addCleanup(p.stop)
        self.device = [{"duracion_seg": 1500, "modo": "W", "epoch": 300, "completada": True},
                       {"duracion_seg": 300, "modo": "T", "completada": True}]          # sin fecha (RTC sin hora)

    def _device_online(self, data):
        return mock.patch.object(esp_client, "_call", lambda *a, **k: (200, "x")), \
            mock.patch.object(esp_client, "_json", lambda *a, **k: data)

    def test_device_mode_shows_app_sessions_too(self):
        c, j = self._device_online(self.device)
        with c, j:
            log = esp_client.get_log("http://dev")
        self.assertEqual([s["epoch"] if "epoch" in s else None for s in log], [None, 200, 300, 400])
        self.assertEqual({s["_src"] for s in log}, {"app", "device"})

    def test_app_mode_keeps_cached_device_sessions(self):
        c, j = self._device_online(self.device)
        with c, j:
            esp_client.get_log("http://dev")                     # se conecta una vez: queda en caché
        log = esp_client.get_log(esp_client.LOCAL)               # y luego, en modo solo app, siguen ahí
        self.assertEqual(len(log), 4)
        self.assertEqual(sum(1 for s in log if s["_src"] == "device"), 2)

    def test_device_offline_falls_back_to_saved(self):
        c, j = self._device_online(self.device)
        with c, j:
            esp_client.get_log("http://dev")
        with mock.patch.object(esp_client, "_call", lambda *a, **k: (0, "")):
            log = esp_client.get_log("http://dev")
        self.assertEqual(len(log), 4)

    def test_empty_everywhere_offline_is_none(self):
        self.engine.log = []
        with mock.patch.object(esp_client, "_call", lambda *a, **k: (0, "")):
            self.assertIsNone(esp_client.get_log("http://dev"))

    def test_tag_goes_to_the_right_source(self):
        c, j = self._device_online(self.device)
        with c, j:
            log = esp_client.get_log("http://dev")
        app_entry = next(s for s in log if s["_src"] == "app" and s["epoch"] == 400)
        self.assertTrue(esp_client.tag_entry(esp_client.LOCAL, app_entry, "Cálculo"))
        self.assertEqual(self.engine.tagged, [(1, "Cálculo")])
        dev_entry = next(s for s in log if s["_src"] == "device" and s.get("epoch") == 300)
        calls = []
        with mock.patch.object(esp_client, "_call", lambda *a, **k: (calls.append(a) or (200, "ok"))):
            self.assertTrue(esp_client.tag_entry("http://dev", dev_entry, "Física"))
        self.assertEqual(calls[0][1], "/etiquetar")
        self.assertEqual(calls[0][2]["indice"], "0")
        cached = esp_client._read_cache()
        self.assertEqual(cached[0]["actividad"], "Física")

    def test_clear_removes_everything(self):
        c, j = self._device_online(self.device)
        with c, j:
            esp_client.get_log("http://dev")
            self.assertTrue(esp_client.clear_log("http://dev"))
        self.assertEqual(self.engine.log, [])
        self.assertEqual(esp_client._read_cache(), [])

    def test_corrupt_cache_ignored(self):
        with open(esp_client._cache_path(), "w") as f:
            f.write("{no json")
        self.assertEqual(len(esp_client.get_log(esp_client.LOCAL)), 2)


def types_ns(**kw):
    import types
    return types.SimpleNamespace(**kw)


if __name__ == "__main__":
    unittest.main()
