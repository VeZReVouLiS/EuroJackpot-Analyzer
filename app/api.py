"""Python <-> JavaScript bridge (exposed as window.pywebview.api)."""
from __future__ import annotations

import json
import threading
import traceback
from datetime import date, datetime, timedelta

from . import generators, rules, stats, updater
from .db import Database
from .paths import resource_dir
from .sources import importer

DEFAULT_SETTINGS = {
    "lang": "el",
    "theme": "dark",
    "auto_update": True,
    "period": "all",
    "columns": 5,
    "algo": generators.AUTO_TICKET,
}


class Api:
    def __init__(self, db: Database):
        self._db = db
        self._window = None
        self._progress = {"running": False, "done": 0, "total": 0, "error": None, "result": None}
        self._lock = threading.Lock()
        self._settings_lock = threading.Lock()

    def _bind(self, window) -> None:
        self._window = window

    # settings ---------------------------------------------------------
    def get_settings(self) -> dict:
        raw = self._db.get_meta("settings")
        s = dict(DEFAULT_SETTINGS)
        if raw:
            try:
                s.update(json.loads(raw))
            except ValueError:
                pass
        return s

    def set_setting(self, key: str, value) -> dict:
        with self._settings_lock:   # read-modify-write must be atomic (UI fires calls concurrently)
            s = self.get_settings()
            if key in DEFAULT_SETTINGS:
                s[key] = value
                self._db.set_meta("settings", json.dumps(s))
            return s

    def get_locale(self, lang: str) -> dict:
        name = lang if lang in ("el", "en") else "en"
        path = resource_dir() / "locales" / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    # state ------------------------------------------------------------
    def get_state(self) -> dict:
        return {
            "count": self._db.count(),
            "last_draw": self._db.last_date(),
            "last_update": self._db.get_meta("last_update"),
            "settings": self.get_settings(),
            "price": rules.COLUMN_PRICE,
            "max_columns": rules.MAX_COLUMNS,
            "algos": generators.ALGOS,
            "euro_max": rules.current_euro_max(),
        }

    # updating ---------------------------------------------------------
    def start_update(self) -> dict:
        with self._lock:
            if self._progress["running"]:
                return self._progress
            self._progress = {"running": True, "done": 0, "total": 0, "error": None, "result": None}
        threading.Thread(target=self._run_update, daemon=True).start()
        return self._progress

    def _run_update(self) -> None:
        def prog(done, total):
            self._progress["done"], self._progress["total"] = done, total

        try:
            res = updater.update(self._db, prog)
            try:
                res["verified"] = updater.verify_with_allwyn(self._db).get("ok")
            except Exception:
                res["verified"] = None
            self._progress["result"] = res
        except Exception as e:  # report to UI, never crash the app
            traceback.print_exc()
            self._progress["error"] = str(e)
        finally:
            self._progress["running"] = False

    def get_progress(self) -> dict:
        return dict(self._progress)

    # statistics -------------------------------------------------------
    @staticmethod
    def _window_for(period: str, last_date: str | None) -> tuple[str | None, str | None]:
        if period in (None, "", "all") or not last_date:
            return None, None
        if period.startswith("custom:"):
            _, a, b = period.split(":")
            return (a or None), (b or None)
        years = {"1y": 1, "3y": 3, "5y": 5, "10y": 10}.get(period)
        if years:
            end = date.fromisoformat(last_date)
            return (end - timedelta(days=365 * years)).isoformat(), None
        return None, None

    def get_stats(self, period: str = "all") -> dict:
        draws = self._db.all_draws()
        since, until = self._window_for(period, self._db.last_date())
        if period and period.startswith("last:"):   # last N draws
            n = int(period.split(":")[1])
            since = draws[-n]["date"] if len(draws) >= n else None
        s = stats.compute(draws, since, until)
        s["recent"] = draws[-10:][::-1]
        return s

    def get_draws(self, limit: int = 100) -> list:
        return self._db.all_draws()[-int(limit):][::-1]

    # tickets ----------------------------------------------------------
    def generate(self, columns: int, algo: str, keep: list | None = None, period: str = "all") -> dict:
        s = self.get_stats(period)
        if not s["n_draws"]:
            raise ValueError("no data")
        keep = [k if k else None for k in (keep or [])]
        return generators.generate_ticket(s, int(columns), algo, keep=keep)

    # import -----------------------------------------------------------
    def import_text(self, filename: str, text: str) -> dict:
        draws = importer.parse_text(text, filename)
        before = self._db.count()
        if draws:
            self._db.upsert_draws(draws)
        return {"found": len(draws), "added": self._db.count() - before, "total": self._db.count()}

    def import_file(self) -> dict | None:
        import webview

        if not self._window:
            return None
        res = self._window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("Data files (*.csv;*.json;*.txt)", "All files (*.*)")
        )
        if not res:
            return None
        draws = importer.parse_file(res[0])
        before = self._db.count()
        if draws:
            self._db.upsert_draws(draws)
        return {"found": len(draws), "added": self._db.count() - before, "total": self._db.count()}

    # window -----------------------------------------------------------
    def toggle_fullscreen(self) -> None:
        if self._window:
            self._window.toggle_fullscreen()

    def today(self) -> str:
        return datetime.now().date().isoformat()
