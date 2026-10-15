"""Dev server for browser testing / docs screenshots (no token): python -m app.devserver 8765"""
from __future__ import annotations

import sys

from .api import Api
from .db import Database
from .server import AppServer


def main(port: int = 8765) -> None:
    srv = AppServer(Api(Database()), port=port, token=None)
    print(f"dev server on {srv.url}")
    srv.httpd.serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
