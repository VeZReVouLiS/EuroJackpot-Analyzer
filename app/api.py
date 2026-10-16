"""Python <-> JavaScript bridge (exposed as window.pywebview.api)."""
from __future__ import annotations

import json
import threading
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

from . import appupdate, countries, evaluation, exporter, generators, rules, stats, updater, version
from .db import Database
from .paths import resource_dir
from .sources import allwyn, importer, official
from .updater import UpdateError

DEFAULT_SETTINGS = {
    "lang": "el",
    "country": "",                # chosen on the splash screen ("" = not chosen yet)
    "prices": {},                 # price per column the user set, by country code
    "theme": "dark",
    "auto_update": True,          # download new draws when the app starts
    "check_app_updates": True,    # look for a new app version (GitHub) when the app starts
    "period": "all",
    "columns": 5,
    "algo": generators.AUTO_TICKET,
}


def _new_progress() -> dict:
    return {"running": False, "done": 0, "total": 0, "error": None, "errors": None, "result": None}


class Api:
    def __init__(self, db: Database):
        self._db = db
        self._window = None
        self._progress = _new_progress()
        self._app_progress = {"running": False, "done": 0, "total": 0, "error": None, "restart": False}
        self._release: dict | None = None
        self._lock = threading.Lock()
        self._settings_lock = threading.Lock()
        self._seed_info = self._load_seed()
        self.evaluate_tickets()

    def _bind(self, window) -> None:
        self._window = window

    # offline seed -----------------------------------------------------
    def _load_seed(self) -> dict | None:
        """Pre-fill an empty database from the snapshot bundled with the app (works offline)."""
        if self._db.count():
            return None
        path = resource_dir() / "seed" / "draws.json"
        if not path.exists():
            return None
        try:
            draws = importer.parse_text(path.read_text(encoding="utf-8"), path.name)
            self._db.upsert_draws(draws)
            self._db.set_meta("seed_loaded", datetime.now().isoformat(timespec="seconds"))
            return {"count": len(draws), "last": self._db.last_date()}
        except Exception:
            traceback.print_exc()
            return None

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
        name = lang if lang in countries.LANGUAGES else "en"
        path = resource_dir() / "locales" / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def get_countries(self) -> dict:
        return countries.catalogue()

    # state ------------------------------------------------------------
    def get_state(self) -> dict:
        return {
            "count": self._db.count(),
            "last_draw": self._db.last_date(),
            "last_update": self._db.get_meta("last_update"),
            "seed": self._seed_info,
            "settings": self.get_settings(),
            "price": countries.effective_price(self.get_settings()),
            "default_price": countries.default_price(self.get_settings().get("country")),
            "max_columns": rules.MAX_COLUMNS,
            "algos": generators.ALGOS,
            "euro_max": rules.current_euro_max(),
            "version": version.__version__,
            "repo_configured": bool(version.GITHUB_REPO),
            "unseen_wins": self.get_tickets()["unseen_wins"],
        }

    # draw-data updating -----------------------------------------------
    def start_update(self) -> dict:
        with self._lock:
            if self._progress["running"]:
                return self._progress
            self._progress = _new_progress()
            self._progress["running"] = True
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
            res["tickets"] = self.evaluate_tickets()      # cross-check saved tickets with the new draws
            self._progress["result"] = res
        except UpdateError as e:       # both sources failed: tell the UI which and why
            self._progress["error"] = str(e)
            self._progress["errors"] = e.errors
        except Exception as e:         # never crash the app
            traceback.print_exc()
            self._progress["error"] = f"{type(e).__name__}: {e}"
        finally:
            self._progress["running"] = False

    def get_progress(self) -> dict:
        return dict(self._progress)

    def diagnose(self) -> list:
        """Check every online source separately (helps when a PC gets 403 etc.)."""
        checks = [
            ("eurojackpot.com", lambda: official.fetch_day(date.fromisoformat(self._db.last_date() or "2026-10-13"))),
            ("allwyn.gr (api.opap.gr)", allwyn.last_draw),
            ("github.com", lambda: appupdate.check("octocat/Hello-World")),
        ]
        out = []
        for name, fn in checks:
            t = time.time()
            try:
                r = fn()
                ok, msg = True, "OK"
                if isinstance(r, dict) and r.get("error") and "latest" in r and r["error"] != "no releases yet":
                    ok, msg = False, r["error"]      # "no releases yet" still proves github.com is reachable
            except Exception as e:
                ok, msg = False, str(e)
            out.append({"name": name, "ok": ok, "message": msg, "ms": int((time.time() - t) * 1000)})
        return out

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

    def get_draw(self, date_str: str) -> dict | None:
        """One draw with prize details (winners worldwide / in Greece, prize per winner)."""
        d = self._db.get_draw(date_str)
        if d:
            d["euro_max"] = rules.euro_max(date.fromisoformat(date_str))
            d["greek_data"] = date_str >= allwyn.FIRST_DATE.isoformat()
        return d

    # tickets ----------------------------------------------------------
    def generate(self, columns: int, algo: str, keep: list | None = None, period: str = "all",
                 ticket_id: int | None = None, target_date: str | None = None) -> dict:
        """Generate a ticket and store it in the history for the next draw.

        While the ticket is still unplayed and unevaluated, generating again with its ``ticket_id`` replaces it
        (so experimenting does not fill the history); a played ticket is never overwritten."""
        s = self.get_stats(period)
        if not s["n_draws"]:
            raise ValueError("no data")
        keep = [k if k else None for k in (keep or [])]
        t = generators.generate_ticket(s, int(columns), algo, keep=keep,
                                       price=countries.effective_price(self.get_settings()))
        existing = self._db.get_ticket(int(ticket_id)) if ticket_id else None
        if existing and not existing["played"] and not existing["result"]:
            target = target_date or existing["target_date"]
            self._db.update_ticket(existing["id"], columns=t["columns"], algo=algo, price=t["total"],
                                   target_date=target)
            tid, played = existing["id"], False
        else:
            target = target_date or rules.next_draw_dates(datetime.now(), 1)[0].isoformat()
            tid = self._db.add_ticket(datetime.now().isoformat(timespec="seconds"), target, algo, t["columns"],
                                      t["total"])
            played = False
        return {**t, "id": tid, "target_date": target, "played": played}

    def get_next_draws(self, n: int = 4) -> list:
        return [d.isoformat() for d in rules.next_draw_dates(datetime.now(), int(n))]

    def set_ticket_played(self, ticket_id: int, played: bool) -> dict | None:
        self._db.update_ticket(int(ticket_id), played=1 if played else 0)
        return self._db.get_ticket(int(ticket_id))

    def set_ticket_target(self, ticket_id: int, target_date: str) -> dict | None:
        t = self._db.get_ticket(int(ticket_id))
        if t and not t["result"]:
            date.fromisoformat(target_date)          # validates
            self._db.update_ticket(t["id"], target_date=target_date)
        return self._db.get_ticket(int(ticket_id))

    def delete_ticket(self, ticket_id: int) -> bool:
        self._db.delete_ticket(int(ticket_id))
        return True

    def evaluate_tickets(self) -> dict:
        """Cross-check every ticket whose draw is now in the database. Returns newly evaluated wins."""
        wins, evaluated = [], 0
        for t in self._db.all_tickets():
            res = t["result"]
            if res and res.get("complete"):
                continue
            draw = self._db.get_draw(t["target_date"])
            if not draw:
                continue
            if res and not draw.get("details"):      # still no prize table: nothing new to learn
                continue
            new = evaluation.evaluate_ticket(t["columns"], draw)
            self._db.update_ticket(t["id"], result=new, seen=0 if (new["winning_columns"] and not res) else int(t["seen"]))
            if not res:
                evaluated += 1
                if new["winning_columns"] and t["played"]:
                    wins.append({"id": t["id"], "target_date": t["target_date"], "total_prize": new["total_prize"]})
        return {"evaluated": evaluated, "wins": wins}

    def get_tickets(self) -> dict:
        tickets = self._db.all_tickets()
        played = [t for t in tickets if t["played"]]
        done = [t for t in played if t["result"]]
        spent = round(sum(t["price"] for t in played), 2)
        won = round(sum(t["result"]["total_prize"] for t in done), 2)
        return {
            "tickets": tickets,
            "totals": {
                "tickets": len(tickets), "played": len(played), "evaluated": len(done),
                "pending": len([t for t in played if not t["result"]]),
                "spent": spent, "won": won, "net": round(won - sum(t["price"] for t in done), 2),
                "best": max([t["result"]["total_prize"] for t in done], default=0.0),
            },
            "unseen_wins": sum(1 for t in tickets if t["played"] and t["result"] and t["result"]["winning_columns"]
                               and not t["seen"]),
        }

    def mark_tickets_seen(self) -> bool:
        for t in self._db.all_tickets():
            if t["result"] and not t["seen"]:
                self._db.update_ticket(t["id"], seen=1)
        return True

    # import / export --------------------------------------------------
    def _import_draws(self, draws: list[dict]) -> dict:
        before = self._db.count()
        if draws:
            self._db.upsert_draws(draws)
            self._db.set_meta("last_import", datetime.now().isoformat(timespec="seconds"))
        self.evaluate_tickets()
        return {"found": len(draws), "added": self._db.count() - before, "total": self._db.count(),
                "last_draw": self._db.last_date()}

    def import_text(self, filename: str, text: str) -> dict:
        res = self._import_draws(importer.parse_text(text, filename))
        res["tickets"] = self._db.import_tickets(importer.parse_tickets(text))
        if res["tickets"]:
            self.evaluate_tickets()
        return res

    def import_file(self) -> dict | None:
        import webview

        if not self._window:
            return None
        res = self._window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("Data files (*.csv;*.json;*.txt)", "All files (*.*)")
        )
        if not res:
            return None
        with open(res[0], "rb") as f:
            raw = f.read()
        return self.import_text(Path(res[0]).name, raw.decode("utf-8-sig", "replace"))

    def export_text(self, fmt: str = "json") -> dict:
        """Export content as text (used by the browser/dev mode, which downloads it itself)."""
        draws = self._db.all_draws(with_details=True)
        text = exporter.to_csv(draws) if fmt == "csv" else exporter.to_json(draws, self._db.all_tickets())
        return {"filename": exporter.default_filename("csv" if fmt == "csv" else "json"), "text": text,
                "count": len(draws)}

    def export_file(self, fmt: str = "json") -> dict | None:
        import webview

        data = self.export_text(fmt)
        if not self._window:
            return None
        res = self._window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=data["filename"],
            file_types=("JSON (*.json)",) if fmt != "csv" else ("CSV (*.csv)",),
        )
        if not res:
            return None
        path = res if isinstance(res, str) else res[0]
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(data["text"])
        return {"path": str(path), "count": data["count"]}

    # application updates (GitHub releases) -----------------------------
    def check_app_update(self) -> dict:
        res = appupdate.check()
        self._release = res if res.get("newer") else None
        res = {k: v for k, v in res.items() if k not in ("zip_url", "sha_url")}
        return res

    def start_app_update(self) -> dict:
        if not self._release:
            return {"error": "no update available"}
        if self._app_progress["running"]:
            return self._app_progress
        self._app_progress = {"running": True, "done": 0, "total": 0, "error": None, "restart": False}
        threading.Thread(target=self._run_app_update, daemon=True).start()
        return self._app_progress

    def _run_app_update(self) -> None:
        def prog(done, total):
            self._app_progress["done"], self._app_progress["total"] = done, total

        try:
            appupdate.install(self._release, prog)
            self._app_progress["restart"] = True
            time.sleep(1.2)               # let the UI show "restarting"
            if self._window:
                self._window.destroy()    # the helper script replaces the files and relaunches
        except Exception as e:
            traceback.print_exc()
            self._app_progress["error"] = str(e)
        finally:
            self._app_progress["running"] = False

    def get_app_update_progress(self) -> dict:
        return dict(self._app_progress)

    def open_url(self, url: str) -> bool:
        """Open a GitHub page in the default browser (only github.com links)."""
        import webbrowser

        if not url.startswith(("https://github.com/", "https://vezrevoulis.github.io/")):
            return False
        return webbrowser.open(url)

    # window -----------------------------------------------------------
    def toggle_fullscreen(self) -> None:
        if self._window:
            self._window.toggle_fullscreen()

    def today(self) -> str:
        return datetime.now().date().isoformat()
