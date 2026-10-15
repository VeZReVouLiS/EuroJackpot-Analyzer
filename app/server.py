"""Local HTTP server: serves the UI and exposes the Api as JSON-RPC (/rpc).

Used (1) as the fallback window when the native pywebview/pythonnet window cannot start, opened in the
system's Edge/Chrome "app mode", and (2) for browser based development (devserver.py).

Security: it only listens on 127.0.0.1, every /rpc and /ping call must carry the per-launch secret token
(a web page you happen to visit cannot read it) and the Host header must be the loopback address
(DNS-rebinding protection).
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .api import Api
from .paths import resource_dir

UI = resource_dir() / "ui"


class AppServer:
    def __init__(self, api: Api, port: int = 0, token: str | None = "auto"):
        self.api = api
        self.token = secrets.token_urlsafe(24) if token == "auto" else token   # None = dev mode, no token
        self.last_ping = 0.0
        self.pinged = False
        self.started = time.time()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self.port = self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/index.html" + (f"?t={self.token}" if self.token else "")

    def _handler(self):
        srv = self

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(UI), **kw)

            def log_message(self, *a):
                pass

            def _allowed(self) -> bool:
                host = (self.headers.get("Host") or "").split(":")[0]
                if host not in ("127.0.0.1", "localhost"):
                    return False
                return srv.token is None or self.headers.get("X-Token") == srv.token

            def _reply(self, code: int, payload: dict):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path.startswith("/ping"):
                    if not self._allowed():
                        return self._reply(403, {"error": "forbidden"})
                    srv.last_ping, srv.pinged = time.time(), True
                    return self._reply(200, {"ok": True})
                host = (self.headers.get("Host") or "").split(":")[0]
                if host not in ("127.0.0.1", "localhost"):
                    return self.send_error(403)
                super().do_GET()

            def do_POST(self):
                if self.path != "/rpc" or not self._allowed():
                    return self._reply(403, {"error": "forbidden"})
                try:
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                    name = body.get("name", "")
                    if name.startswith("_") or not hasattr(srv.api, name):
                        raise AttributeError(name)
                    out = {"result": getattr(srv.api, name)(*body.get("args", []))}
                except Exception as e:
                    out = {"error": str(e)}
                self._reply(200, out)

        return Handler

    def start(self) -> None:
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def wait_until_window_closed(self, first_ping_timeout: float = 300, idle_timeout: float = 8) -> None:
        """Block until the browser window stops sending heartbeats (it was closed)."""
        while True:
            time.sleep(1)
            now = time.time()
            if self.pinged and now - self.last_ping > idle_timeout:
                return
            if not self.pinged and now - self.started > first_ping_timeout:
                return

    def stop(self) -> None:
        self.httpd.shutdown()
