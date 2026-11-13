import json
import unittest
import urllib.error
import urllib.request

import bridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.state = {"modo": "T", "ejecutando": True, "segundos": 90, "bloqueoActivo": True}
        self.on = True
        self.sites = ["youtube.com"]
        self.srv = bridge.start(lambda: self.state, lambda: self.on, port=0, add_site=self._add)
        self.port = self.srv.server_address[1]

    def _add(self, data):
        import sites
        self.sites, ok = sites.add(self.sites, data.get("dominio"))
        return {"added": int(ok), "total": len(self.sites)}

    def post(self, body, headers=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/sitios", data=json.dumps(body).encode(),
                                     method="POST", headers={"Content-Type": "application/json", **(headers or {})})
        return urllib.request.urlopen(req, timeout=3)

    def test_add_site(self):
        r = self.post({"dominio": "https://www.Twitch.tv/directory"}, {"X-Focus-Relay": "1"})
        self.assertEqual(json.loads(r.read()), {"added": 1, "total": 2})
        self.assertEqual(self.sites, ["youtube.com", "twitch.tv"])
        r = self.post({"dominio": "twitch.tv"}, {"X-Focus-Relay": "1"})                  # repetido
        self.assertEqual(json.loads(r.read())["added"], 0)
        r = self.post({"dominio": "no es un dominio"}, {"X-Focus-Relay": "1"})
        self.assertEqual(json.loads(r.read())["added"], 0)

    def test_post_needs_custom_header(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.post({"dominio": "twitch.tv"})
        self.assertEqual(cm.exception.code, 403)
        self.assertEqual(self.sites, ["youtube.com"])

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def get(self, path="/estado", host=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        if host:
            req.add_header("Host", host)
        return urllib.request.urlopen(req, timeout=3)

    def test_serves_state(self):
        r = self.get()
        self.assertEqual(json.loads(r.read())["segundos"], 90)
        self.assertIsNone(r.headers.get("Access-Control-Allow-Origin"))

    def test_disabled_and_missing(self):
        self.on = False
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get()
        self.assertEqual(cm.exception.code, 404)
        self.on = True
        self.state = None
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get()
        self.assertEqual(cm.exception.code, 503)

    def test_rejects_foreign_host_and_other_paths(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get(host="evil.example.com")
        self.assertEqual(cm.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/datos")
        self.assertEqual(cm.exception.code, 404)

    def test_change_port(self):
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]
        s.close()
        self.assertTrue(bridge.set_port(free))
        self.port = free
        self.assertEqual(json.loads(self.get().read())["segundos"], 90)
        busy = socket.socket()
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        self.assertFalse(bridge.set_port(busy.getsockname()[1]))     # ocupado: vuelve al anterior
        self.assertEqual(json.loads(self.get().read())["segundos"], 90)
        busy.close()
        self.srv = bridge._current["srv"]                              # tearDown cierra el vigente


if __name__ == "__main__":
    unittest.main()
