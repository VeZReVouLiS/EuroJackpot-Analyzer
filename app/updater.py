"""Initial history download + incremental updates."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable

from . import rules
from .db import Database
from .sources import allwyn, official

Progress = Callable[[int, int], None]


def update(db: Database, progress: Progress | None = None, today: date | None = None) -> dict:
    """Fetch every draw missing from the DB. Returns a summary dict."""
    today = today or date.today()
    first_run = db.count() == 0
    last = db.last_date()
    start = rules.FIRST_DRAW if first_run else date.fromisoformat(last) - timedelta(days=7)
    existing = db.existing_dates()
    source = "eurojackpot.com"
    try:
        # on first run: everything; later: re-check the last week + anything new
        skip = existing if first_run else {d for d in existing if d < (date.fromisoformat(last)).isoformat()}
        draws = official.fetch_range(start, today, skip=skip, progress=progress)
    except ConnectionError:
        # fallback to Allwyn (only covers 2024-03-08 onward)
        source = "allwyn.gr"
        draws = allwyn.fetch_range(max(start, allwyn.FIRST_DATE), today)
    added = sum(1 for d in draws if d["date"] not in existing)
    if draws:
        db.upsert_draws(draws)
    db.set_meta("last_update", datetime.now().isoformat(timespec="seconds"))
    return {"added": added, "total": db.count(), "last_draw": db.last_date(), "source": source}


def verify_with_allwyn(db: Database) -> dict:
    """Cross-check the latest Allwyn draw against the stored one."""
    a = allwyn.last_draw()
    if not a:
        return {"ok": None}
    mine = next((d for d in reversed(db.all_draws()) if d["date"] == a["date"]), None)
    return {"ok": bool(mine and mine["main"] == a["main"] and mine["euro"] == a["euro"]), "date": a["date"]}
