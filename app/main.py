"""Entry point.

Normal mode: native window (pywebview + WebView2).
Fallback mode: if that cannot start (e.g. pythonnet / .NET problems on some PCs) the UI is served from a
local server and opened in Edge/Chrome "app mode" (a chrome-less window). Force it with --browser.
"""
from __future__ import annotations

import os
import subprocess
import sys
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

from .api import Api
from .db import Database
from .paths import data_dir, resource_dir
from .server import AppServer
from .unblock import unblock_app


def _log(msg: str) -> None:
    try:
        with open(data_dir() / "startup.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except OSError:
        pass


def _run_native(api: Api) -> None:
    n = unblock_app()            # downloaded-from-internet flag blocks pythonnet on some PCs; must precede the import
    if n:
        _log(f"removed the internet-download flag from {n} files")
    import webview

    index = resource_dir() / "ui" / "index.html"
    window = webview.create_window(
        "EuroJackpot Analyzer", url=str(index), js_api=api, width=1320, height=860,
        min_size=(900, 600), background_color="#0b1020",
    )
    api._bind(window)
    storage = data_dir() / "webview"
    storage.mkdir(exist_ok=True)
    webview.start(storage_path=str(storage), private_mode=False, debug="--debug" in sys.argv)


def _find_browser() -> str | None:
    roots = [os.environ.get(k) for k in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData")]
    rel = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"]
    for r in rel:
        for root in roots:
            if root and Path(root, r).exists():
                return str(Path(root, r))
    return None


def _run_browser(api: Api) -> None:
    server = AppServer(api)
    server.start()
    exe = _find_browser()
    if exe:
        profile = data_dir() / "browser-profile"      # own profile: separate window, closes independently
        subprocess.Popen([exe, f"--app={server.url}", f"--user-data-dir={profile}", "--window-size=1320,860",
                          "--no-first-run", "--no-default-browser-check"])
    else:
        webbrowser.open(server.url)                   # last resort: a normal browser tab
    server.wait_until_window_closed()
    server.stop()


def main() -> None:
    db = Database()
    api = Api(db)
    try:
        if "--browser" in sys.argv:
            _run_browser(api)
        else:
            try:
                _run_native(api)
            except Exception:
                _log("native window failed, using browser fallback:\n" + traceback.format_exc())
                _run_browser(api)
    finally:
        db.close()


if __name__ == "__main__":
    main()
