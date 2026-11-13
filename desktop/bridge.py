"""Puente local para la extensión de navegador: sirve el estado de la sesión en http://127.0.0.1:8765/estado.

Estado de la sesión (GET /estado) y «bloquear este sitio» (POST /sitios, solo agrega), solo desde este equipo (127.0.0.1). La extensión lo consulta cuando no encuentra el dispositivo,
así iniciar una sesión en la app activa también el bloqueo de sitios y la música del navegador. No envía CORS,
de modo que una página web cualquiera no puede leerlo; la extensión sí, por sus permisos de host.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
_ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def host_ok(header, port=PORT):
    """Solo se acepta el Host esperado (evita que una web lo lea por 'DNS rebinding')."""
    name = (header or "").rsplit(":", 1)[0] if ":" in (header or "") else (header or "")
    return name in _ALLOWED_HOSTS


def make_handler(get_state, enabled, add_site=None):
    class Handler(BaseHTTPRequestHandler):
        timeout = 5                      # una conexión que no envía nada no deja colgado un hilo
        def log_message(self, *args):
            pass

        def _send(self, code, body=b"", ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self):
            if not host_ok(self.headers.get("Host")):
                return self._send(403)
            path = self.path.split("?")[0]
            if not enabled() or path != "/estado":
                return self._send(404)
            state = get_state()
            if not state:
                return self._send(503)
            self._send(200, json.dumps(state).encode("utf-8"))
        do_HEAD = do_GET

        def do_POST(self):
            """La extensión pide bloquear el sitio de la pestaña actual (solo agrega). Exige una cabecera propia: una web
            ajena no puede enviarla sin permiso previo (preflight CORS), que este servidor nunca concede."""
            if not host_ok(self.headers.get("Host")):
                return self._send(403)
            if self.path.split("?")[0] != "/sitios" or not enabled() or not add_site:
                return self._send(404)
            if self.headers.get("X-Focus-Relay") != "1":
                return self._send(403)
            try:
                size = int(self.headers.get("Content-Length") or 0)
                if not 0 < size <= 20_000:
                    return self._send(413)
                data = json.loads(self.rfile.read(size).decode("utf-8"))
                result = add_site(data if isinstance(data, dict) else {})
            except (ValueError, UnicodeDecodeError):
                return self._send(400)
            self._send(200, json.dumps(result).encode("utf-8"))
    return Handler


_current = {"srv": None, "port": None, "get_state": None, "enabled": None, "add_site": None}


def start(get_state, enabled, port=PORT, add_site=None):
    """Arranca el servidor en un hilo. Devuelve el servidor, o None si el puerto está ocupado."""
    _current.update(get_state=get_state, enabled=enabled, add_site=add_site)
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(get_state, enabled, add_site))
    except OSError as exc:
        print(f"[Focus Relay] puente con la extensión no disponible (puerto {port}): {exc}")
        return None
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _current.update(srv=srv, port=srv.server_address[1])
    return srv


def _stop():
    srv, _current["srv"] = _current.get("srv"), None
    if srv:
        srv.shutdown()
        srv.server_close()


def set_port(port):
    """Cambia el puerto en caliente. True si quedó escuchando en el nuevo; si está ocupado vuelve al anterior y da False."""
    old = _current.get("port")
    if port == old and _current.get("srv"):
        return True
    _stop()
    keep = (_current["get_state"], _current["enabled"])
    extra = dict(add_site=_current["add_site"])
    if start(*keep, port, **extra):
        return True
    if old:
        start(*keep, old, **extra)
    return False
