"""Official EuroJackpot results (Lotto Hessen WL_InfoService) - full history since 2012-03-23."""
from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Callable

from .. import rules

URL = (
    "https://www.eurojackpot.com/wlinfo/WL_InfoService"
    "?client=jsn&gruppe=ZahlenUndQuoten&spielart=EJ&datum={d}"
)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) EuroJackpotApp/1.0"


def parse(payload: dict) -> dict | None:
    """Return {'date','main','euro','source'} or None when there is no draw on that day."""
    if not payload or payload.get("error") or "head" not in payload:
        return None
    try:
        rows = payload["zahlen"]["hauptlotterie"]["ziehungen"]
        main = [int(x) for x in rows[0]["zahlen"]]
        euro = [int(x) for x in rows[1]["zahlen"]]
        d = payload["head"]["datum"]
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    if len(main) != 5 or len(euro) != 2:
        return None
    return {"date": d, "main": sorted(main), "euro": sorted(euro), "source": "eurojackpot.com"}


def fetch_day(d: date, retries: int = 3, timeout: int = 25) -> dict | None:
    req = urllib.request.Request(URL.format(d=d.isoformat()), headers={"User-Agent": UA})
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return parse(json.loads(r.read().decode("utf-8")))
        except Exception as e:  # network / json errors -> retry
            last_err = e
            time.sleep(0.6 * (attempt + 1))
    raise ConnectionError(f"official source failed for {d}: {last_err}")


def fetch_range(
    start: date,
    end: date,
    skip: set[str] | None = None,
    progress: Callable[[int, int], None] | None = None,
    workers: int = 8,
) -> list[dict]:
    skip = skip or set()
    days = [d for d in rules.candidate_dates(start, end) if d.isoformat() not in skip]
    out: list[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(fetch_day, days):
            done += 1
            if res:
                out.append(res)
            if progress:
                progress(done, len(days))
    return out
