"""Draw-data updates: initial history download, incremental updates, details backfill.

This is about the *draw results* only. Updating the application itself lives in appupdate.py.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable

from . import rules
from .db import Database
from .sources import allwyn, official
from .sources.http import SourceError

Progress = Callable[[int, int], None]


class UpdateError(Exception):
    """Both sources failed. ``errors`` maps source name -> reason."""

    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))


def _attach_greek_details(draws: list[dict]) -> None:
    """Merge Greek winners (Allwyn API, 2024+) into the official details. Best effort."""
    recent = [d for d in draws if d["date"] >= allwyn.FIRST_DATE.isoformat()]
    if not recent:
        return
    try:
        first = date.fromisoformat(min(d["date"] for d in recent))
        last = date.fromisoformat(max(d["date"] for d in recent))
        by_date = {d["date"]: d for d in allwyn.fetch_range(first, last)}
    except SourceError:
        return
    for d in recent:
        a = by_date.get(d["date"])
        if a:
            d["details"] = allwyn.merge_details(d.get("details"), a["details"])


def update(db: Database, progress: Progress | None = None, today: date | None = None) -> dict:
    """Fetch every draw (or its details) missing from the DB. Returns a summary dict."""
    today = today or date.today()
    existing = db.existing_dates()
    no_details = db.dates_missing_details()
    if db.get_meta("backfill_attempt") == today.isoformat():
        no_details = set()       # already tried today (e.g. imported data without details): don't hammer
    first_run = not existing
    last = db.last_date()
    start = rules.FIRST_DRAW if (first_run or no_details) else date.fromisoformat(last) - timedelta(days=7)
    if no_details and not first_run:
        start = min(start, date.fromisoformat(min(no_details)))
    # skip what we already have complete, except the most recent week (results can be corrected)
    recheck_from = (date.fromisoformat(last) - timedelta(days=7)).isoformat() if last else "9999"
    skip = {d for d in existing if d < recheck_from and d not in no_details}

    errors: dict[str, str] = {}
    source = "eurojackpot.com"
    try:
        draws = official.fetch_range(start, today, skip=skip, progress=progress)
        _attach_greek_details(draws)
    except SourceError as e:
        errors["eurojackpot.com"] = str(e)
        source = "allwyn.gr"
        try:
            draws = allwyn.fetch_range(max(start, allwyn.FIRST_DATE), today)
        except SourceError as e2:
            errors["allwyn.gr"] = str(e2)
            raise UpdateError(errors) from e2
    added = sum(1 for d in draws if d["date"] not in existing)
    if draws:
        db.upsert_draws(draws)
    if no_details:
        db.set_meta("backfill_attempt", today.isoformat())
    db.set_meta("last_update", datetime.now().isoformat(timespec="seconds"))
    return {"added": added, "total": db.count(), "last_draw": db.last_date(), "source": source,
            "backfilled": len(no_details & {d["date"] for d in draws})}


def verify_with_allwyn(db: Database) -> dict:
    """Cross-check the latest Allwyn draw against the stored one."""
    a = allwyn.last_draw()
    if not a:
        return {"ok": None}
    mine = db.get_draw(a["date"])
    return {"ok": bool(mine and mine["main"] == a["main"] and mine["euro"] == a["euro"]), "date": a["date"]}
