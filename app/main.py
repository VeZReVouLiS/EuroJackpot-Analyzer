"""Entry point: opens the app window (pywebview / WebView2)."""
from __future__ import annotations

import sys

import webview

from .api import Api
from .db import Database
from .paths import data_dir, resource_dir


def main() -> None:
    db = Database()
    api = Api(db)
    index = resource_dir() / "ui" / "index.html"
    window = webview.create_window(
        "EuroJackpot Analyzer",
        url=str(index),
        js_api=api,
        width=1320,
        height=860,
        min_size=(900, 600),
        background_color="#0b1020",
    )
    api._bind(window)
    storage = data_dir() / "webview"
    storage.mkdir(exist_ok=True)
    webview.start(storage_path=str(storage), private_mode=False, debug="--debug" in sys.argv)
    db.close()


if __name__ == "__main__":
    main()
