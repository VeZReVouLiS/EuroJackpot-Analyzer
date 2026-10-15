"""Allwyn (ex-OPAP) draws API. EuroJackpot = game 5149, available only since 2024-03-08 (Greece joined)."""
from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

BASE = "https://api.opap.gr/draws/v3.0/5149"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) EuroJackpotApp/1.0"
FIRST_DATE = date(2024, 3, 8)


def _get(path: str, retries: int = 3, timeout: int = 25):
    req = urllib.request.Request(f"{BASE}/{path}", headers={"User-Agent": UA})
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8")
                return json.loads(body) if body else None
        except Exception as e:
            last = e
            time.sleep(0.6 * (attempt + 1))
    raise ConnectionError(f"allwyn api failed for {path}: {last}")


def parse(draw: dict) -> dict | None:
    """Convert one Allwyn draw JSON into our draw dict (None when results are not available)."""
    if not draw or draw.get("status") != "results":
        return None
    wn = draw.get("winningNumbers") or {}
    main, euro = wn.get("list") or [], wn.get("bonus") or []
    if len(main) != 5 or len(euro) != 2:
        return None
    # draws take place ~21:00 Greek/Finnish time (UTC+2/+3): +3h keeps the correct calendar day
    dt = datetime.fromtimestamp(draw["drawTime"] / 1000, tz=timezone.utc) + timedelta(hours=3)
    return {"date": dt.date().isoformat(), "main": sorted(main), "euro": sorted(euro), "source": "allwyn.gr"}


def fetch_draw(draw_id: int) -> dict | None:
    return parse(_get(str(draw_id)))


def fetch_range(start: date, end: date, workers: int = 6) -> list[dict]:
    start = max(start, FIRST_DATE)
    if start > end:
        return []
    ids: list[int] = []
    # the API groups by month: iterate month by month
    cur = date(start.year, start.month, 1)
    while cur <= end:
        nxt = date(cur.year + (cur.month // 12), cur.month % 12 + 1, 1)
        last = nxt - timedelta(days=1)
        res = _get(f"draw-date/{cur.isoformat()}/{last.isoformat()}/draw-id")
        ids.extend(res or [])
        cur = nxt
    with ThreadPoolExecutor(max_workers=workers) as ex:
        draws = [d for d in ex.map(fetch_draw, ids) if d]
    return [d for d in draws if start.isoformat() <= d["date"] <= end.isoformat()]


def last_draw() -> dict | None:
    res = _get("last-result-and-active")
    return parse(res["last"]) if res and res.get("last") else None
