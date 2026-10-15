"""Dev server: serves the UI over HTTP and exposes the Api as JSON-RPC (/rpc). Used for browser testing."""
from __future__ import annotations

import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .api import Api
from .db import Database
from .paths import resource_dir

UI = resource_dir() / "ui"


def make_handler(api: Api):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(UI), **kw)

        def log_message(self, *a):  # quiet
            pass

        def do_POST(self):
            if self.path != "/rpc":
                self.send_error(404)
                return
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            name = body.get("name", "")
            try:
                if name.startswith("_") or not hasattr(api, name):
                    raise AttributeError(name)
                out = {"result": getattr(api, name)(*body.get("args", []))}
            except Exception as e:
                out = {"error": str(e)}
            data = json.dumps(out).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main(port: int = 8765) -> None:
    api = Api(Database())
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(api))
    print(f"dev server on http://127.0.0.1:{port}")
    srv.serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
